import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:uuid/uuid.dart';
import '../models/models.dart';
import 'field_storage_service.dart';

/// Service for managing drone scan bookings with Supabase database according to public.bookings schema:
/// - booking_id (UUID PK)
/// - fid (UUID FK users)
/// - fieldid (UUID FK fields)
/// - field_name (TEXT)
/// - booking_datetime (TIMESTAMP)
/// - created_at (TIMESTAMPTZ)
/// - status (TEXT, default 'Pending')
class BookingService {
  SupabaseClient get _supabase => Supabase.instance.client;

  String _getStorageKey(String? fid) =>
      fid != null && fid.isNotEmpty ? 'agrivyaan_bookings_$fid' : 'agrivyaan_bookings_local';

  /// Fetch all drone scan bookings for the given farmer FID.
  Future<List<DroneScan>> loadBookings(String fid) async {
    if (!FieldStorageService.isUuid(fid)) {
      return await _loadLocalBookings(fid);
    }

    try {
      final response = await _supabase
          .from('bookings')
          .select()
          .eq('fid', fid)
          .order('booking_datetime', ascending: false);

      final List<dynamic> data = response as List<dynamic>;
      final bookings = data
          .map((json) => _droneScanFromMap(json as Map<String, dynamic>))
          .toList();

      // Cache locally per user
      await _cacheBookingsLocally(fid, bookings);
      return bookings;
    } catch (e) {
      debugPrint('Error loading bookings from Supabase: $e');
      return await _loadLocalBookings(fid);
    }
  }

  /// Create a new booking in Supabase.
  Future<DroneScan?> createBooking({
    required String fid,
    required String fieldId,
    String? fieldName,
    required String scanType,
    required DateTime bookingDatetime,
    String status = 'Pending',
    String? operatorName,
  }) async {
    final formattedDate = DateFormat('yyyy-MM-dd').format(bookingDatetime);
    final formattedTime = DateFormat('hh:mm a').format(bookingDatetime);
    final createdAt = DateTime.now().toUtc();

    var scan = DroneScan(
      id: const Uuid().v4(),
      fid: fid,
      fieldId: fieldId,
      fieldName: fieldName,
      bookingDatetime: bookingDatetime,
      createdAt: createdAt,
      scanType: scanType,
      date: formattedDate,
      time: formattedTime,
      operatorName: operatorName ?? 'Pending Assignment',
      status: _statusFromString(status),
      verificationStatus: 'PENDING',
      healthScore: 80,
    );

    // Exact Supabase public.bookings table columns
    final mapData = <String, dynamic>{
      'fid': fid,
      'fieldid': fieldId,
      'field_name': fieldName,
      'booking_datetime': bookingDatetime.toIso8601String(),
      'created_at': createdAt.toIso8601String(),
      'status': status,
    };

    try {
      debugPrint('Inserting booking into Supabase: $mapData');
      final saved = await _supabase
          .from('bookings')
          .insert(mapData)
          .select()
          .single();

      if (saved['booking_id'] != null) {
        scan = scan.copyWith(id: saved['booking_id'].toString());
      }
      final savedCreatedAt = DateTime.tryParse(saved['created_at']?.toString() ?? '');
      if (savedCreatedAt != null) {
        scan = scan.copyWith(createdAt: savedCreatedAt);
      }
      debugPrint('Booking created in Supabase successfully! ID: ${scan.id}');
    } catch (e) {
      debugPrint('Supabase booking insert error: $e');
    }

    // Cache locally
    final local = await _loadLocalBookings(fid);
    local.insert(0, scan);
    await _cacheBookingsLocally(fid, local);

    return scan;
  }

  /// Update booking status in Supabase.
  Future<void> updateBookingStatus(
    String bookingId,
    DroneScanStatus newStatus, {
    String? operatorName,
    String? verificationStatus,
    int? healthScore,
  }) async {
    try {
      final statusString = _statusToString(newStatus);
      final updateData = <String, dynamic>{
        'status': statusString,
      };

      await _supabase
          .from('bookings')
          .update(updateData)
          .eq('booking_id', bookingId);
      debugPrint('Updated booking $bookingId status to: $statusString in Supabase');
    } catch (e) {
      debugPrint('Error updating booking status in Supabase: $e');
    }
  }

  Future<bool> cancelBooking(DroneScan scan, String fid) async {
    if (!scan.canCancelAt(DateTime.now())) return false;

    if (FieldStorageService.isUuid(fid)) {
      try {
        final updated = await _supabase
            .from('bookings')
            .update({'status': 'Cancelled'})
            .eq('booking_id', scan.id)
            .eq('fid', fid)
            .select('booking_id')
            .maybeSingle();
        if (updated == null) return false;
      } catch (e) {
        debugPrint('Error cancelling booking ${scan.id} in Supabase: $e');
        return false;
      }
    }

    final cancelledScan = scan.copyWith(status: DroneScanStatus.cancelled);
    final local = await _loadLocalBookings(fid);
    final index = local.indexWhere((booking) => booking.id == scan.id);
    if (index == -1) {
      local.insert(0, cancelledScan);
    } else {
      local[index] = cancelledScan;
    }
    await _cacheBookingsLocally(fid, local);
    return true;
  }

  // --- Local Cache Helpers ---
  Future<void> _cacheBookingsLocally(String? fid, List<DroneScan> bookings) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonList = bookings.map((s) => _droneScanToMap(s)).toList();
      await prefs.setString(_getStorageKey(fid), jsonEncode(jsonList));
    } catch (_) {}
  }

  Future<List<DroneScan>> _loadLocalBookings(String? fid) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonString = prefs.getString(_getStorageKey(fid));
      if (jsonString == null || jsonString.isEmpty) return [];
      final List<dynamic> jsonList = jsonDecode(jsonString) as List<dynamic>;
      return jsonList
          .map((item) => _droneScanFromMap(item as Map<String, dynamic>))
          .toList();
    } catch (_) {
      return [];
    }
  }

  static DroneScanStatus _statusFromString(String statusStr) {
    final lower = statusStr.toLowerCase();
    if (lower.contains('cancel')) {
      return DroneScanStatus.cancelled;
    } else if (lower.contains('pend') || lower.contains('request')) {
      return DroneScanStatus.requested;
    } else if (lower.contains('sched') || lower.contains('confirm')) {
      return DroneScanStatus.scheduled;
    } else if (lower.contains('assign') || lower.contains('pilot')) {
      return DroneScanStatus.droneAssigned;
    } else if (lower.contains('progress') || lower.contains('fly')) {
      return DroneScanStatus.inProgress;
    } else if (lower.contains('process')) {
      return DroneScanStatus.processing;
    } else if (lower.contains('analysis') || lower.contains('ai')) {
      return DroneScanStatus.aiAnalysis;
    } else if (lower.contains('verify') || lower.contains('review')) {
      return DroneScanStatus.verification;
    } else if (lower.contains('ready') || lower.contains('complete') || lower.contains('done')) {
      return DroneScanStatus.reportReady;
    }
    return DroneScanStatus.requested;
  }

  static String _statusToString(DroneScanStatus status) {
    switch (status) {
      case DroneScanStatus.requested:
        return 'Pending';
      case DroneScanStatus.scheduled:
        return 'Scheduled';
      case DroneScanStatus.droneAssigned:
        return 'Pilot Assigned';
      case DroneScanStatus.inProgress:
        return 'In Progress';
      case DroneScanStatus.processing:
        return 'Processing';
      case DroneScanStatus.aiAnalysis:
        return 'AI Analysis';
      case DroneScanStatus.verification:
        return 'Under Review';
      case DroneScanStatus.reportReady:
        return 'Completed';
      case DroneScanStatus.cancelled:
        return 'Cancelled';
    }
  }

  static DroneScan _droneScanFromMap(Map<String, dynamic> json) {
    final bookingId = (json['booking_id'] ?? json['id'] ?? '').toString();
    final fid = (json['fid'] ?? '').toString();
    final fieldId = (json['fieldid'] ?? json['field_id'] ?? '').toString();
    final fieldName = json['field_name']?.toString();
    final statusStr = (json['status'] ?? 'Pending').toString();
    final status = _statusFromString(statusStr);
    final createdAt = DateTime.tryParse(json['created_at']?.toString() ?? '');

    DateTime? dt;
    final dtVal = json['booking_datetime'] ?? json['date'];
    if (dtVal != null) {
      dt = DateTime.tryParse(dtVal.toString());
    }

    String dateStr = 'Today';
    String timeStr = '10:00 AM';
    if (dt != null) {
      dateStr = DateFormat('yyyy-MM-dd').format(dt);
      timeStr = DateFormat('hh:mm a').format(dt);
    } else {
      dateStr = (json['date'] ?? '2026-08-27').toString();
      timeStr = (json['time'] ?? '10:00 AM').toString();
    }

    return DroneScan(
      id: bookingId,
      fid: fid,
      fieldId: fieldId,
      fieldName: fieldName,
      bookingDatetime: dt,
      createdAt: createdAt,
      scanType: (json['scan_type'] ?? 'Crop Health Scan').toString(),
      date: dateStr,
      time: timeStr,
      operatorName: (json['operator_name'] ?? 'Pending Assignment').toString(),
      status: status,
      verificationStatus: (json['verification_status'] ?? 'PENDING').toString(),
      healthScore: (json['health_score'] as num?)?.toInt() ?? 80,
      aiReportData: json['ai_report_data'] as Map<String, dynamic>?,
    );
  }

  static Map<String, dynamic> _droneScanToMap(DroneScan scan) => {
        'booking_id': scan.id,
        'fid': scan.fid,
        'fieldid': scan.fieldId,
        'field_name': scan.fieldName,
        'booking_datetime': scan.bookingDatetime?.toIso8601String() ?? scan.date,
        'created_at': scan.createdAt?.toIso8601String(),
        'scan_type': scan.scanType,
        'date': scan.date,
        'time': scan.time,
        'operator_name': scan.operatorName,
        'status': _statusToString(scan.status),
        'verification_status': scan.verificationStatus,
        'health_score': scan.healthScore,
        'ai_report_data': scan.aiReportData,
      };
}
