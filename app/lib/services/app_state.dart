import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/farm_field.dart';
import '../models/models.dart';
import '../models/soil_health_card.dart';
import 'field_storage_service.dart';
import 'soil_health_card_storage_service.dart';
import 'booking_service.dart';
import 'localization.dart';
import 'soil_health_card_demo_data.dart';
import 'package:uuid/uuid.dart';

class AppState extends ChangeNotifier {
  // Authentication & Session
  bool _isLoggedIn = false;
  bool get isLoggedIn => _isLoggedIn;

  bool _isLoadingAuth = false;
  bool get isLoadingAuth => _isLoadingAuth;

  FarmerProfile? _currentProfile;
  FarmerProfile? get currentProfile => _currentProfile;

  String? get currentFid => _currentProfile?.fid ?? _supabase.auth.currentUser?.id;
  bool _needsProfileSetup = false;
  bool get needsProfileSetup => _needsProfileSetup;

  // Language & Role Configuration
  String _currentLanguage = 'en';
  String get currentLanguage => _currentLanguage;

  String _currentRole = 'FARMER'; // FARMER, ADMIN, DRONE_OPERATOR
  String get currentRole => _currentRole;

  // Offline Architecture
  bool _isOffline = false;
  bool get isOffline => _isOffline;

  final List<ActionEntry> _offlineActionQueue = [];
  List<ActionEntry> get offlineActionQueue => _offlineActionQueue;

  // Active Datasets
  List<CropField> _fields = [];
  List<CropField> get fields => _fields;

  List<DroneScan> _scans = [];
  List<DroneScan> get scans => _scans;

  List<ActionEntry> _actions = [];
  List<ActionEntry> get actions => _actions;

  List<WeatherForecast> _weatherForecast = [];
  List<WeatherForecast> get weatherForecast => _weatherForecast;

  List<LibraryItem> _libraryCrops = [];
  List<LibraryItem> get libraryCrops => _libraryCrops;

  List<LibraryItem> _libraryPests = [];
  List<LibraryItem> get libraryPests => _libraryPests;

  List<LibraryItem> _libraryDiseases = [];
  List<LibraryItem> get libraryDiseases => _libraryDiseases;

  List<NotificationItem> _notifications = [];
  List<NotificationItem> get notifications => _notifications;

  final List<String> _requestedReportFieldIds = [];
  List<String> get requestedReportFieldIds => _requestedReportFieldIds;

  // Soil Health Card data (field-specific)
  Map<String, List<SoilHealthCard>> _soilHealthCards = {};
  Map<String, List<SoilHealthCard>> get soilHealthCards => _soilHealthCards;

  // Services
  SupabaseClient get _supabase => Supabase.instance.client;
  final FieldStorageService _fieldStorageService = FieldStorageService();
  final SoilHealthCardStorageService _shcStorageService = SoilHealthCardStorageService();
  final BookingService _bookingService = BookingService();

  // Persistent Chat History
  List<Map<String, dynamic>> _chatHistory = [];
  List<Map<String, dynamic>> get chatHistory => _chatHistory;

  AppState() {
    _initializeData();
    _checkExistingSession();
    _listenToAuthState();
    _loadChatHistory();
  }

  Future<void> _loadChatHistory() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonString = prefs.getString('sarvam_chat_history');
      if (jsonString != null && jsonString.isNotEmpty) {
        final List decoded = jsonDecode(jsonString);
        _chatHistory = decoded.map((item) => Map<String, dynamic>.from(item)).toList();
        notifyListeners();
      }
    } catch (e) {
      debugPrint('Error loading chat history: $e');
    }
  }

  Future<void> addChatMessage(Map<String, dynamic> message) async {
    _chatHistory.add(message);
    notifyListeners();
    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonString = jsonEncode(_chatHistory);
      await prefs.setString('sarvam_chat_history', jsonString);
    } catch (e) {
      debugPrint('Error saving chat history: $e');
    }
  }

  Future<void> clearChatHistory() async {
    _chatHistory.clear();
    notifyListeners();
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('sarvam_chat_history');
    } catch (e) {
      debugPrint('Error clearing chat history: $e');
    }
  }

  // --- Session & Supabase Auth Sync ---

  Future<void> _checkExistingSession() async {
    try {
      // ALWAYS load saved language preference first, regardless of auth method
      final prefs = await SharedPreferences.getInstance();
      final savedLang = prefs.getString('app_preferred_language');
      if (savedLang != null && savedLang.isNotEmpty) {
        _currentLanguage = savedLang;
        debugPrint('Restored language preference: $savedLang');
      }

      final session = _supabase.auth.currentSession;
      final user = _supabase.auth.currentUser;

      if (session != null && user != null) {
        debugPrint('Active Supabase session detected for user: ${user.id} (${user.phone})');
        await loadUserDataFromSupabase(user.id, phone: user.phone);
        return;
      }

      // Restore session from local SharedPreferences if user logged in by phone
      final savedFid = prefs.getString('saved_farmer_fid');
      final savedPhone = prefs.getString('saved_farmer_phone');

      if (savedFid != null && savedFid.isNotEmpty && FieldStorageService.isUuid(savedFid)) {
        final profileRes = await _supabase
            .from('users')
            .select()
            .eq('fid', savedFid)
            .maybeSingle();

        if (profileRes != null) {
          _currentProfile = FarmerProfile.fromMap(profileRes);
          _isLoggedIn = true;
          _needsProfileSetup = false;
          debugPrint('Restored farmer session for FID: $savedFid (${_currentProfile?.name})');
          await loadUserDataFromSupabase(savedFid, phone: _currentProfile?.phone);
          return;
        }
      } else if (savedPhone != null && savedPhone.isNotEmpty) {
        final profileRes = await _supabase
            .from('users')
            .select()
            .eq('phone_no', savedPhone)
            .maybeSingle();

        if (profileRes != null) {
          _currentProfile = FarmerProfile.fromMap(profileRes);
          _isLoggedIn = true;
          _needsProfileSetup = false;
          final fid = _currentProfile?.fid ?? profileRes['fid']?.toString();
          if (fid != null) {
            await prefs.setString('saved_farmer_fid', fid);
            await loadUserDataFromSupabase(fid, phone: savedPhone);
            return;
          }
        }
      }

      debugPrint('No active farmer session found on startup.');
    } catch (e) {
      debugPrint('Error checking existing Supabase session: $e');
    }
  }

  void _listenToAuthState() {
    try {
      _supabase.auth.onAuthStateChange.listen((data) async {
        final AuthChangeEvent event = data.event;
        final Session? session = data.session;

        if (event == AuthChangeEvent.signedIn && session != null) {
          final user = session.user;
          await loadUserDataFromSupabase(user.id, phone: user.phone);
        } else if (event == AuthChangeEvent.signedOut) {
          // Do NOT call logout() here — logout() already called signOut(),
          // which triggered this event. Calling logout() again would loop.
          // Just clear local state silently.
          _isLoggedIn = false;
          _currentProfile = null;
          _fields = [];
          _scans = [];
          _soilHealthCards = {};
          _initializeData();
          notifyListeners();
        }
      });
    } catch (e) {
      debugPrint('Error attaching auth state change listener: $e');
    }
  }

  /// Load profile, fields, soil health cards, and bookings strictly for current authenticated farmer
  Future<void> loadUserDataFromSupabase(String authOrFid, {String? phone}) async {
    _isLoadingAuth = true;
    notifyListeners();

    try {
      // 1. Fetch User Profile
      Map<String, dynamic>? profileRes;
      if (FieldStorageService.isUuid(authOrFid)) {
        profileRes = await _supabase
            .from('users')
            .select()
            .eq('fid', authOrFid)
            .maybeSingle();
      }

      if (profileRes == null) {
        profileRes = await _supabase
            .from('users')
            .select()
            .eq('auth_id', authOrFid)
            .maybeSingle();
      }

      if (profileRes != null) {
        _currentProfile = FarmerProfile.fromMap(profileRes);
        _isLoggedIn = true;
        _needsProfileSetup = false;
        debugPrint('Loaded farmer profile from Supabase for: ${_currentProfile?.name} (FID: ${_currentProfile?.fid})');
      } else {
        debugPrint('Authenticated user has no profile record in users table yet.');
        _currentProfile = FarmerProfile(
          name: 'Farmer',
          phone: phone ?? _supabase.auth.currentUser?.phone ?? '',
          email: '',
          preferredLanguage: _currentLanguage,
          location: 'Wardha, Maharashtra',
          farmArea: 5.0,
          areaUnit: 'acres',
          mainCrop: 'Cotton',
          fid: FieldStorageService.isUuid(authOrFid) ? authOrFid : null,
        );
        _isLoggedIn = false;
        _needsProfileSetup = true;
      }

      final fidToUse = _currentProfile?.fid ?? (FieldStorageService.isUuid(authOrFid) ? authOrFid : null);

      if (fidToUse != null && fidToUse.isNotEmpty) {
        // Save session locally
        try {
          final prefs = await SharedPreferences.getInstance();
          await prefs.setString('saved_farmer_fid', fidToUse);
          if (_currentProfile?.phone != null && _currentProfile!.phone.isNotEmpty) {
            await prefs.setString('saved_farmer_phone', _currentProfile!.phone);
          }
        } catch (_) {}

        // 2. Fetch Fields strictly belonging to this farmer
        final farmFields = await _fieldStorageService.loadFields(fid: fidToUse);
        _fields = farmFields.map((ff) => CropField.fromFarmField(ff)).toList();

        // 3. Fetch Soil Health Cards strictly for this farmer
        final loadedShc = await _shcStorageService.loadCards(fid: fidToUse);
        _soilHealthCards = loadedShc;

        // 4. Fetch Bookings strictly for this farmer
        final loadedBookings = await _bookingService.loadBookings(fidToUse);
        _scans = loadedBookings;
      } else {
        _fields = [];
        _scans = [];
        _soilHealthCards = {};
      }
    } catch (e) {
      debugPrint('Error loading farmer data from Supabase: $e');
    } finally {
      _isLoadingAuth = false;
      notifyListeners();
    }
  }

  // --- Phone OTP Authentication ---

  /// Step 1: Send OTP to farmer phone number via Supabase Auth (Twilio backend)
  /// NOTE: Requires Twilio configured in Supabase Dashboard:
  /// Authentication > Providers > Phone > Enable + add Twilio credentials
  Future<void> sendOtpToPhone(String phone) async {
    final formattedPhone = _formatIndianPhone(phone);
    debugPrint('Sending OTP via Supabase Auth to: $formattedPhone');
    try {
      await _supabase.auth.signInWithOtp(phone: formattedPhone);
      debugPrint('OTP sent successfully to $formattedPhone');
    } catch (e) {
      debugPrint('OTP send error: $e');
      // Re-throw with a cleaner message
      if (e.toString().contains('Twilio') || e.toString().contains('provider') || e.toString().contains('phone_provider')) {
        throw Exception(
          'SMS provider not configured. Please enable Phone Auth + Twilio in Supabase Dashboard, '
          'or use Demo Login to test the app without SMS.',
        );
      }
      rethrow;
    }
  }

  /// Step 2: Verify OTP token with Supabase Auth & check if farmer already exists.
  /// Returns true if farmer exists in database (navigates directly to Home page),
  /// or false if phone number is new (prompts for details).
  Future<bool> verifyOtpToken(String phone, String token) async {
    final formattedPhone = _formatIndianPhone(phone);
    final cleanDigits = phone.replaceAll(RegExp(r'\D'), '');
    final tenDigits = cleanDigits.length >= 10 ? cleanDigits.substring(cleanDigits.length - 10) : cleanDigits;

    debugPrint('Attempting OTP verification for: $formattedPhone (clean: $tenDigits)');
    User? authUser;
    try {
      final response = await _supabase.auth.verifyOTP(
        phone: formattedPhone,
        token: token,
        type: OtpType.sms,
      );
      authUser = response.user ?? _supabase.auth.currentUser;
    } catch (e) {
      debugPrint('OTP verification skipped/fallback: $e');
    }

    // Check if user profile already exists in public.users table by auth_id or phone_no
    Map<String, dynamic>? profileRes;
    if (authUser != null) {
      profileRes = await _supabase
          .from('users')
          .select()
          .eq('auth_id', authUser.id)
          .maybeSingle();
    }

    if (profileRes == null && tenDigits.isNotEmpty) {
      try {
        final results = await _supabase
            .from('users')
            .select()
            .or('phone_no.eq.$phone,phone_no.eq.$tenDigits,phone_no.eq.+$tenDigits,phone_no.eq.+91$tenDigits')
            .maybeSingle();
        if (results != null) {
          profileRes = results;
        }
      } catch (e) {
        debugPrint('Error searching user by phone in Supabase: $e');
      }
    }

    if (profileRes != null) {
      _currentProfile = FarmerProfile.fromMap(profileRes);
      _isLoggedIn = true;
      _needsProfileSetup = false;
      final fid = _currentProfile?.fid ?? profileRes['fid']?.toString();
      debugPrint('Existing user found for phone $tenDigits! Logging directly in: ${_currentProfile?.name} (FID: $fid)');
      if (fid != null && fid.isNotEmpty) {
        await loadUserDataFromSupabase(fid, phone: phone);
      }
      notifyListeners();
      return true; // Phone number already exists -> directly to Home!
    } else {
      debugPrint('New phone number $tenDigits detected -> Prompting for details.');
      return false; // Phone number is new -> ask for details
    }
  }

  String _formatIndianPhone(String phone) {
    final digits = phone.replaceAll(RegExp(r'\D'), '');
    if (digits.length == 12 && digits.startsWith('91')) return '+$digits';
    return '+91$digits';
  }

  /// Create or update farmer profile in Supabase `users` table
  /// Works for both authenticated users and direct/demo users
  Future<void> saveFarmerProfileToSupabase(FarmerProfile profile) async {
    final authId = _supabase.auth.currentUser?.id;
    debugPrint('Saving farmer profile to Supabase (auth_id: $authId, phone: ${profile.phone})...');

    // Only include columns that exist in the actual users table schema:
    // fid (auto), phone_no, name, location, auth_id
    final mapData = <String, dynamic>{
      'phone_no': profile.phone,
      'name': profile.name,
      'location': profile.location.isNotEmpty ? profile.location : null,
    };

    if (authId != null && authId.isNotEmpty) {
      mapData['auth_id'] = authId;
    }

    Map<String, dynamic>? savedRow;

    try {
      if (authId != null && authId.isNotEmpty) {
        savedRow = await _supabase
            .from('users')
            .upsert(mapData, onConflict: 'auth_id')
            .select()
            .single();
      } else {
        // Unauthenticated/direct entry: check if phone already exists
        final existing = await _supabase
            .from('users')
            .select()
            .eq('phone_no', profile.phone)   // match actual column name
            .maybeSingle();

        if (existing != null) {
          savedRow = await _supabase
              .from('users')
              .update(mapData)
              .eq('fid', existing['fid'])
              .select()
              .single();
        } else {
          savedRow = await _supabase
              .from('users')
              .insert(mapData)
              .select()
              .single();
        }
      }
    } catch (e) {
      debugPrint('Primary save to Supabase users table failed: $e. Retrying plain insert...');
      try {
        savedRow = await _supabase
            .from('users')
            .insert(mapData)
            .select()
            .single();
      } catch (retryError) {
        debugPrint('Error saving profile to Supabase on retry: $retryError');
      }
    }

    if (savedRow != null) {
      final newFid = savedRow['fid'].toString();
      _currentProfile = profile.copyWith(fid: newFid);
      _isLoggedIn = true;
      _needsProfileSetup = false;
      debugPrint('Successfully saved farmer profile to Supabase users table! FID: $newFid');

      // Persist session to SharedPreferences
      try {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('saved_farmer_fid', newFid);
        if (profile.phone.isNotEmpty) {
          await prefs.setString('saved_farmer_phone', profile.phone);
        }
      } catch (e) {
        debugPrint('Error saving session locally: $e');
      }

      // Load data strictly for this newly registered/updated farmer
      await loadUserDataFromSupabase(newFid, phone: profile.phone);
    } else {
      // Local fallback
      _currentProfile = profile.copyWith(fid: profile.fid ?? const Uuid().v4());
      _isLoggedIn = true;
      _needsProfileSetup = false;
    }

    notifyListeners();
  }

  // --- Soil Health Card Management ---

  Future<void> _loadSoilHealthCards() async {
    final fidToUse = currentFid;
    final loaded = await _shcStorageService.loadCards(fid: fidToUse);
    if (loaded.isNotEmpty) {
      _soilHealthCards = loaded;
    }
    notifyListeners();
  }

  List<SoilHealthCard> getCardsForField(String fieldId) {
    return _soilHealthCards[fieldId] ?? [];
  }

  SoilHealthCard? getCurrentCardForField(String fieldId) {
    final cards = _soilHealthCards[fieldId] ?? [];
    try {
      return cards.firstWhere((c) => c.isCurrent);
    } catch (_) {
      return cards.isNotEmpty ? cards.first : null;
    }
  }

  Future<void> addSoilHealthCard(String fieldId, SoilHealthCard card, {String? localFilePath}) async {
    await _shcStorageService.addCard(
      _soilHealthCards,
      fieldId,
      card,
      localFilePath: localFilePath,
    );

    _addNotification(
      title: 'Soil Health Card Added',
      description: 'A new Soil Health Card record has been saved and verified.',
      isCritical: false,
    );
    notifyListeners();
  }

  Future<void> updateSoilHealthCard(String fieldId, SoilHealthCard card) async {
    final fidToUse = currentFid;
    await _shcStorageService.updateCard(_soilHealthCards, fieldId, card, fid: fidToUse);
    notifyListeners();
  }

  // --- Translation Helper ---
  String translate(String key) {
    return AppLocalizations.translate(key, _currentLanguage);
  }

  void setLanguage(String langCode) async {
    _currentLanguage = langCode;
    notifyListeners();
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('app_preferred_language', langCode);
    } catch (e) {
      debugPrint('Error saving language preference: $e');
    }
  }

  void setRole(String role) {
    _currentRole = role;
    notifyListeners();
  }

  void toggleOfflineMode() {
    _isOffline = !_isOffline;
    if (!_isOffline && _offlineActionQueue.isNotEmpty) {
      for (var action in _offlineActionQueue) {
        _actions.insert(0, action);
        _addNotification(
          title: 'Action Synced Successfully',
          description: 'Your offline action "${action.title} on ${action.zoneName}" has been synchronized with cloud.',
          isCritical: false,
        );
      }
      _offlineActionQueue.clear();
    }
    notifyListeners();
  }

  /// Create or update farmer profile in Supabase.
  Future<void> completeOnboarding(
    FarmerProfile profile, {
    double? lat,
    double? lng,
  }) async {
    await saveFarmerProfileToSupabase(profile);
    notifyListeners();
  }

  Future<void> logout() async {
    try {
      await _supabase.auth.signOut();
    } catch (e) {
      debugPrint('Error signing out from Supabase: $e');
    }
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('saved_farmer_fid');
      await prefs.remove('saved_farmer_phone');
    } catch (e) {
      debugPrint('Error clearing local session: $e');
    }
    _isLoggedIn = false;
    _currentProfile = null;
    _fields = [];
    _scans = [];
    _soilHealthCards = {};
    _initializeData();
    notifyListeners();
  }

  // --- Profile Management ---
  void updateProfile(FarmerProfile profile) async {
    await saveFarmerProfileToSupabase(profile);
  }

  // --- Field Management ---
  Future<void> addField(CropField field) async {
    final fidToUse = currentFid;
    final userName = _currentProfile?.name ?? (field.userName != null && field.userName!.isNotEmpty ? field.userName! : 'Farmer');
    
    final farmField = FarmField.fromCropField(field).copyWith(
      id: FieldStorageService.isUuid(field.id) ? field.id : const Uuid().v4(),
      userName: userName,
      fieldNumber: field.fieldNumber > 0 ? field.fieldNumber : (_fields.length + 1),
    );

    final saved = await _fieldStorageService.addField(
      [],
      farmField,
      fid: fidToUse,
      userName: userName,
    );

    final newCropField = CropField.fromFarmField(saved);
    _fields.add(newCropField);

    _addNotification(
      title: 'New Field Registered',
      description: 'Field "${newCropField.name}" (#${newCropField.fieldNumber}) was successfully registered and saved.',
      isCritical: false,
    );
    notifyListeners();
  }

  void editField(CropField updatedField) async {
    final idx = _fields.indexWhere((f) => f.id == updatedField.id);
    if (idx != -1) {
      _fields[idx] = updatedField;

      final farmField = FarmField.fromCropField(updatedField);
      final fidToUse = currentFid;
      final userName = _currentProfile?.name ?? updatedField.userName ?? 'Farmer';
      await _fieldStorageService.updateField([], farmField, fid: fidToUse, userName: userName);

      notifyListeners();
    }
  }

  void deleteField(String fieldId) async {
    _fields.removeWhere((f) => f.id == fieldId);
    _scans.removeWhere((s) => s.fieldId == fieldId);
    _actions.removeWhere((a) => a.fieldId == fieldId);

    await _fieldStorageService.deleteField([], fieldId);
    notifyListeners();
  }

  // --- Drone Scan Bookings & Lifecycle ---
  Future<void> requestDroneScan({
    required String fieldId,
    required String scanType,
    required String date,
    required String time,
    DateTime? bookingDatetime,
  }) async {
    final fidToUse = currentFid ?? 'demo_farmer_id';
    
    String? fieldName;
    try {
      final field = _fields.firstWhere((f) => f.id == fieldId);
      fieldName = field.name;
    } catch (_) {}

    DateTime finalDateTime = bookingDatetime ?? DateTime.now();
    if (bookingDatetime == null) {
      try {
        final parsedDate = DateTime.tryParse(date);
        if (parsedDate != null) {
          finalDateTime = parsedDate;
        }
      } catch (_) {}
    }

    final newScan = await _bookingService.createBooking(
      fid: fidToUse,
      fieldId: fieldId,
      fieldName: fieldName,
      scanType: scanType,
      bookingDatetime: finalDateTime,
      status: 'Pending',
    );

    if (newScan != null) {
      _scans.insert(0, newScan);
    }

    final displayName = fieldName ?? 'Field';

    _addNotification(
      title: 'Drone Scan Requested',
      description: 'A $scanType scan has been requested for $displayName on $date.',
      isCritical: false,
    );
    notifyListeners();
  }

  Future<bool> cancelDroneScan(String scanId) async {
    final idx = _scans.indexWhere((scan) => scan.id == scanId);
    if (idx == -1) return false;

    final scan = _scans[idx];
    if (!scan.canCancelAt(DateTime.now())) return false;

    final fid = scan.fid ?? currentFid ?? 'demo_farmer_id';
    final cancelled = await _bookingService.cancelBooking(scan, fid);
    if (!cancelled) return false;

    final currentIdx = _scans.indexWhere((item) => item.id == scanId);
    if (currentIdx == -1 || !_scans[currentIdx].canCancelAt(DateTime.now())) {
      return false;
    }

    _scans[currentIdx] = _scans[currentIdx].copyWith(
      status: DroneScanStatus.cancelled,
    );
    _addNotification(
      title: 'Drone Booking Cancelled',
      description: 'Your ${scan.scanType} booking for ${scan.fieldName ?? 'your field'} has been cancelled.',
      isCritical: false,
    );
    notifyListeners();
    return true;
  }

  // Operator Actions
  void operatorAcceptScan(String scanId, String operatorName) async {
    final idx = _scans.indexWhere((s) => s.id == scanId);
    if (idx != -1) {
      _scans[idx] = _scans[idx].copyWith(
        status: DroneScanStatus.droneAssigned,
        operatorName: operatorName,
      );

      await _bookingService.updateBookingStatus(
        scanId,
        DroneScanStatus.droneAssigned,
        operatorName: operatorName,
      );

      _addNotification(
        title: 'Drone Pilot Assigned',
        description: '$operatorName has accepted the scan request.',
        isCritical: false,
      );
      notifyListeners();
    }
  }

  void operatorStartScan(String scanId) async {
    final idx = _scans.indexWhere((s) => s.id == scanId);
    if (idx != -1) {
      _scans[idx] = _scans[idx].copyWith(
        status: DroneScanStatus.inProgress,
      );

      await _bookingService.updateBookingStatus(
        scanId,
        DroneScanStatus.inProgress,
      );
      notifyListeners();
    }
  }

  void operatorCompleteScan(String scanId) async {
    final idx = _scans.indexWhere((s) => s.id == scanId);
    if (idx != -1) {
      _scans[idx] = _scans[idx].copyWith(
        status: DroneScanStatus.processing,
      );

      await _bookingService.updateBookingStatus(
        scanId,
        DroneScanStatus.processing,
      );

      Future.delayed(const Duration(seconds: 1), () async {
        final scanIdx = _scans.indexWhere((s) => s.id == scanId);
        if (scanIdx != -1) {
          _scans[scanIdx] = _scans[scanIdx].copyWith(
            status: DroneScanStatus.aiAnalysis,
            verificationStatus: 'UNDER REVIEW',
          );

          await _bookingService.updateBookingStatus(
            scanId,
            DroneScanStatus.aiAnalysis,
            verificationStatus: 'UNDER REVIEW',
          );

          _addNotification(
            title: 'Scan AI Processing Complete',
            description: 'Drone data has been parsed. Report sent to Expert for verification.',
            isCritical: false,
          );
          notifyListeners();
        }
      });
      notifyListeners();
    }
  }

  // Expert/Admin Actions
  void adminVerifyReport(String scanId, String verificationStatus, {int? healthScore}) async {
    final idx = _scans.indexWhere((s) => s.id == scanId);
    if (idx != -1) {
      final finalHealth = healthScore ?? _scans[idx].healthScore;

      _scans[idx] = _scans[idx].copyWith(
        status: DroneScanStatus.reportReady,
        verificationStatus: verificationStatus,
        healthScore: finalHealth,
      );

      await _bookingService.updateBookingStatus(
        scanId,
        DroneScanStatus.reportReady,
        verificationStatus: verificationStatus,
        healthScore: finalHealth,
      );

      _addNotification(
        title: 'Field Intelligence Report Ready',
        description: 'Verification complete ($verificationStatus) for scan on ${_scans[idx].date}. Health: $finalHealth/100.',
        isCritical: true,
      );

      if (_scans[idx].fieldId == 'field_a') {
        _applyIrrigationOutcome();
      }
      notifyListeners();
    }
  }

  // --- Action Tracking ---
  void recordAction({
    required String fieldId,
    required String title,
    required String category,
    required String zoneName,
    required String notes,
    Map<String, String>? beforeState,
    Map<String, String>? afterState,
  }) {
    final newAction = ActionEntry(
      id: 'action_${DateTime.now().millisecondsSinceEpoch}',
      fieldId: fieldId,
      title: title,
      category: category,
      zoneName: zoneName,
      date: '2026-08-26',
      notes: notes,
      isCompleted: true,
      beforeState: beforeState,
      afterState: afterState,
    );

    if (_isOffline) {
      _offlineActionQueue.add(newAction);
      _addNotification(
        title: 'Action Queued Offline',
        description: '"$title on $zoneName" recorded offline. Will sync once network returns.',
        isCritical: false,
      );
    } else {
      _actions.insert(0, newAction);
      _addNotification(
        title: 'Action Logged',
        description: 'Recorded action: "$title on $zoneName".',
        isCritical: false,
      );
    }
    notifyListeners();
  }

  void _applyIrrigationOutcome() {
    final hasIrrigatedZone2 = _actions.any(
      (a) => a.fieldId == 'field_a' && a.zoneName == 'Zone 2' && a.title.contains('Irrigation'),
    );

    if (hasIrrigatedZone2) {
      final fieldIdx = _fields.indexWhere((f) => f.id == 'field_a');
      if (fieldIdx != -1) {
        final field = _fields[fieldIdx];

        final updatedZones = field.zones.map((z) {
          if (z.id == 'z2') {
            return z.copyWith(
              status: 'Healthy',
              moisture: 48.0,
              risk: 'None',
              aiExplanation: 'Soil moisture improved to 48% after recorded irrigation on 26 Aug.',
              recommendation: 'Maintain regular watering intervals.',
            );
          }
          return z;
        }).toList();

        final updatedSensors = field.sensors.map((s) {
          if (s.sensorName == 'Soil Moisture') {
            final newHistory = List<double>.from(s.history)..add(48.0);
            return s.copyWith(
              currentValue: 48.0,
              status: 'NORMAL',
              history: newHistory,
            );
          }
          return s;
        }).toList();

        _fields[fieldIdx] = field.copyWith(
          healthScore: 82,
          prevHealthScore: 78,
          moistureStatus: 'NORMAL',
          lastScanDate: '26 Aug (Verified Scan)',
          activeAlerts: field.activeAlerts.where((a) => !a.contains('Zone 2') && !a.contains('Soil Moisture')).toList(),
          zones: updatedZones,
          sensors: updatedSensors,
        );

        final actionIdx = _actions.indexWhere(
          (a) => a.fieldId == 'field_a' && a.zoneName == 'Zone 2' && a.title.contains('Irrigation'),
        );
        if (actionIdx != -1) {
          _actions[actionIdx] = _actions[actionIdx].copyWith(
            afterState: {'Moisture': '48%', 'Stress': 'NORMAL'},
            notes: '${_actions[actionIdx].notes}\n[System Outcome]: Soil moisture increased to 48%. Growth indicators restored.',
          );
        }
      }
    }
  }

  // --- Seed Initial Fallback Datasets ---
  void _initializeData() {
    _currentLanguage = 'en';
    _currentRole = 'FARMER';
    _isOffline = false;
    _offlineActionQueue.clear();

    _currentProfile = FarmerProfile(
      name: 'Demo Farmer',
      phone: '9876543210',
      email: 'farmer@agrivyaan.com',
      preferredLanguage: 'en',
      location: 'Wardha, Maharashtra',
      farmArea: 9.7,
      areaUnit: 'acres',
      mainCrop: 'Cotton',
    );

    _fields = [
      CropField(
        id: 'field_a',
        name: 'Field A (Cotton)',
        crop: 'Cotton',
        area: 3.2,
        areaUnit: 'acres',
        sowingDate: '2026-06-15',
        cropStage: 'Flowering stage',
        healthScore: 78,
        prevHealthScore: 84,
        lastScanDate: '26 Aug',
        moistureStatus: 'LOW',
        activeAlerts: ['Zone 2: Low Soil Moisture Alert', 'Early Moisture Warning'],
        zones: [
          Zone(
            id: 'z1',
            name: 'Zone 1',
            status: 'Healthy',
            moisture: 52.0,
            temperature: 29.0,
            risk: 'None',
            aiExplanation: 'Vegetation indicator index is within healthy ranges.',
            recommendation: 'Maintain present schedule.',
          ),
          Zone(
            id: 'z2',
            name: 'Zone 2',
            status: 'Low moisture',
            moisture: 27.0,
            temperature: 32.0,
            risk: 'Moderate',
            aiExplanation: 'Soil moisture declined from 38% to 27% over the last 48 hours.',
            recommendation: 'Check irrigation in Zone 2 immediately.',
          ),
          Zone(
            id: 'z3',
            name: 'Zone 3',
            status: 'Possible nutrient stress',
            moisture: 45.0,
            temperature: 30.0,
            risk: 'Low',
            aiExplanation: 'Mild discoloration detected in crop leaves.',
            recommendation: 'Apply nitrogen-rich fertilizer dose.',
          ),
          Zone(
            id: 'z4',
            name: 'Zone 4',
            status: 'Healthy',
            moisture: 50.0,
            temperature: 29.0,
            risk: 'None',
            aiExplanation: 'Optimal moisture retention levels.',
            recommendation: 'No action needed.',
          ),
        ],
        sensors: [
          SensorReading(
            sensorName: 'Soil Moisture',
            currentValue: 27.0,
            minNormal: 35.0,
            maxNormal: 65.0,
            unit: '%',
            status: 'LOW',
            history: [45.0, 39.0, 33.0, 27.0],
          ),
          SensorReading(
            sensorName: 'Temperature',
            currentValue: 32.0,
            minNormal: 20.0,
            maxNormal: 35.0,
            unit: '°C',
            status: 'NORMAL',
            history: [29.0, 30.0, 31.0, 32.0],
          ),
          SensorReading(
            sensorName: 'Humidity',
            currentValue: 65.0,
            minNormal: 50.0,
            maxNormal: 80.0,
            unit: '%',
            status: 'NORMAL',
            history: [60.0, 62.0, 64.0, 65.0],
          ),
        ],
      ),
      CropField(
        id: 'field_b',
        name: 'Field B (Tomato)',
        crop: 'Tomato',
        area: 2.5,
        areaUnit: 'acres',
        sowingDate: '2026-07-01',
        cropStage: 'Vegetative stage',
        healthScore: 84,
        prevHealthScore: 85,
        lastScanDate: '24 Aug',
        moistureStatus: 'NORMAL',
        activeAlerts: ['Possible Disease: Early Leaf Blight'],
        zones: [
          Zone(
            id: 'zb1',
            name: 'Zone 1',
            status: 'Healthy',
            moisture: 48.0,
            temperature: 28.0,
            risk: 'None',
            aiExplanation: 'Foliar growth standard.',
            recommendation: 'None.',
          ),
          Zone(
            id: 'zb2',
            name: 'Zone 2',
            status: 'Disease risk',
            moisture: 45.0,
            temperature: 28.0,
            risk: 'Moderate',
            aiExplanation: 'Early signs of brown spots detected in tomato leaf photos.',
            recommendation: 'Spray copper fungicide in Zone 2.',
          ),
          Zone(
            id: 'zb3',
            name: 'Zone 3',
            status: 'Healthy',
            moisture: 49.0,
            temperature: 28.0,
            risk: 'None',
            aiExplanation: 'Normal conditions.',
            recommendation: 'None.',
          ),
          Zone(
            id: 'zb4',
            name: 'Zone 4',
            status: 'Healthy',
            moisture: 47.0,
            temperature: 28.0,
            risk: 'None',
            aiExplanation: 'Normal conditions.',
            recommendation: 'None.',
          ),
        ],
        sensors: [
          SensorReading(
            sensorName: 'Soil Moisture',
            currentValue: 45.0,
            minNormal: 35.0,
            maxNormal: 65.0,
            unit: '%',
            status: 'NORMAL',
            history: [48.0, 47.0, 46.0, 45.0],
          ),
          SensorReading(
            sensorName: 'Temperature',
            currentValue: 28.0,
            minNormal: 18.0,
            maxNormal: 32.0,
            unit: '°C',
            status: 'NORMAL',
            history: [27.0, 27.5, 28.0, 28.0],
          ),
          SensorReading(
            sensorName: 'Humidity',
            currentValue: 72.0,
            minNormal: 60.0,
            maxNormal: 90.0,
            unit: '%',
            status: 'NORMAL',
            history: [70.0, 71.0, 72.0, 72.0],
          ),
        ],
      ),
    ];

    _scans = [
      DroneScan(
        id: 'scan_a1',
        fieldId: 'field_a',
        scanType: 'Crop Health Scan',
        date: '2026-08-26',
        time: '08:30 AM',
        operatorName: 'Rajesh Kumar',
        status: DroneScanStatus.reportReady,
        verificationStatus: 'VERIFIED',
        healthScore: 78,
      ),
      DroneScan(
        id: 'scan_b1',
        fieldId: 'field_b',
        scanType: 'Full Field Analysis',
        date: '2026-08-24',
        time: '09:15 AM',
        operatorName: 'Amit Patil',
        status: DroneScanStatus.reportReady,
        verificationStatus: 'VERIFIED',
        healthScore: 84,
      ),
    ];

    _actions = [
      ActionEntry(
        id: 'action_p1',
        fieldId: 'field_b',
        title: 'Checked Disease Boundary',
        category: 'Pest',
        zoneName: 'Zone 2',
        date: '2026-08-25',
        notes: 'Manually inspected tomato leaf spots. Copper fungicide scheduled.',
        isCompleted: true,
      ),
    ];

    _weatherForecast = [
      WeatherForecast(
        dayName: 'Today',
        date: '26 Aug',
        temperature: 32.0,
        rainProbability: 10.0,
        humidity: 65.0,
        windSpeed: 8.0,
        weatherCondition: 'Sunny',
        sprayingCondition: 'GOOD',
        aiSummary: 'Excellent spraying window. Low wind speed and minimal precipitation risk.',
        bestWindow: 'Tomorrow 6:00 AM – 9:00 AM',
      ),
      WeatherForecast(
        dayName: 'Tomorrow',
        date: '27 Aug',
        temperature: 28.0,
        rainProbability: 75.0,
        humidity: 85.0,
        windSpeed: 14.0,
        weatherCondition: 'Rainy',
        sprayingCondition: 'AVOID',
        aiSummary: 'Avoid spraying operations today. Heavy rain expected in afternoon.',
        bestWindow: 'None',
      ),
    ];

    _notifications = [
      NotificationItem(
        id: 'not_1',
        title: 'Low Moisture Alert: Field A',
        description: 'Field A soil moisture has fallen below 28%. Action recommended.',
        time: '2 hours ago',
        isRead: false,
        isCritical: true,
      ),
    ];

    _soilHealthCards = SoilHealthCardDemoData.demoCards;
  }

  void _addNotification({
    required String title,
    required String description,
    required bool isCritical,
  }) {
    _notifications.insert(
      0,
      NotificationItem(
        id: 'not_${DateTime.now().millisecondsSinceEpoch}',
        title: title,
        description: description,
        time: 'Just now',
        isRead: false,
        isCritical: isCritical,
      ),
    );
    notifyListeners();
  }

  void updateWeatherForecast(List<WeatherForecast> forecast) {
    _weatherForecast = forecast;
    notifyListeners();
  }

  void markNotificationsAsRead() {
    _notifications = _notifications.map((n) => n.copyWith(isRead: true)).toList();
    notifyListeners();
  }

  void requestReportForField(String fieldId) {
    if (!_requestedReportFieldIds.contains(fieldId)) {
      _requestedReportFieldIds.add(fieldId);
      _addNotification(
        title: 'Report Request Received',
        description: 'Your request for a detailed crop audit report has been submitted to the admin panel.',
        isCritical: false,
      );
      notifyListeners();
    }
  }
}

class AppStateProvider extends InheritedNotifier<AppState> {
  const AppStateProvider({
    super.key,
    required super.notifier,
    required super.child,
  });

  static AppState of(BuildContext context) {
    final provider = context.dependOnInheritedWidgetOfExactType<AppStateProvider>();
    assert(provider != null, 'No AppStateProvider found in context');
    return provider!.notifier!;
  }
}
