import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/soil_health_card.dart';

/// Service for managing Soil Health Card records with Supabase database & storage
/// and local storage fallback.
class SoilHealthCardStorageService {
  static const String _storageKey = 'agrivyaan_soil_health_cards';

  SupabaseClient get _supabase => Supabase.instance.client;

  /// Loads all saved Soil Health Cards from Supabase (or local storage fallback).
  /// Returns a map of fieldId -> list of SoilHealthCard records.
  Future<Map<String, List<SoilHealthCard>>> loadCards({String? fid}) async {
    final currentFid = fid ?? _supabase.auth.currentUser?.id;

    if (currentFid != null && currentFid.isNotEmpty) {
      try {
        final ownFields = await _supabase
            .from('fields')
            .select('fieldid')
            .eq('fid', currentFid);
        final fieldIds = (ownFields as List<dynamic>)
            .map((field) => field['fieldid'].toString())
            .toList();
        if (fieldIds.isEmpty) return {};
        final response = await _supabase
            .from('soil_health')
            .select()
            .inFilter('fieldid', fieldIds);

        final List<dynamic> data = response as List<dynamic>;
        final Map<String, List<SoilHealthCard>> result = {};

        for (final item in data) {
          final card = _soilHealthCardFromMap(item as Map<String, dynamic>);
          final fieldId = card.fieldId;
          if (!result.containsKey(fieldId)) {
            result[fieldId] = [];
          }
          result[fieldId]!.add(card);
        }

        // Cache locally
        await saveCards(result);
        return result;
      } catch (e) {
        debugPrint('Error fetching soil health cards from Supabase: $e');
      }
    }

    // Fallback to local storage
    return await _loadLocalCards();
  }

  /// Uploads a report file to Supabase Storage bucket `soil-reports`
  Future<String?> uploadReportFile(String filePath, String fieldId) async {
    try {
      final file = File(filePath);
      if (!await file.exists()) return null;

      final fileName = '${DateTime.now().millisecondsSinceEpoch}_${filePath.split(Platform.pathSeparator).last}';
      final storagePath = '$fieldId/$fileName';

      await _supabase.storage.from('soil-reports').upload(storagePath, file);
      final publicUrl = _supabase.storage.from('soil-reports').getPublicUrl(storagePath);
      debugPrint('Soil report uploaded successfully to Supabase Storage: $publicUrl');
      return publicUrl;
    } catch (e) {
      debugPrint('Error uploading soil report file to Supabase Storage: $e');
      return null;
    }
  }

  /// Adds a single card for a field and persists to Supabase & local cache.
  Future<void> addCard(
    Map<String, List<SoilHealthCard>> allCards,
    String fieldId,
    SoilHealthCard card, {
    String? localFilePath,
  }) async {
    String? fileUrl;

    if (localFilePath != null && localFilePath.isNotEmpty) {
      fileUrl = await uploadReportFile(localFilePath, fieldId);
    }

    final cardWithUrl = fileUrl != null ? card.copyWith(sourceFileName: fileUrl) : card;

    // Insert first so the UI only confirms after Supabase accepts the values.
    final inserted = await _supabase
        .from('soil_health')
        .insert(_soilHealthCardToMap(cardWithUrl))
        .select('shid')
        .single();
    final savedCard = cardWithUrl.copyWith(id: inserted['shid'].toString());

    // Update local map after the database insert succeeds.
    final fieldCards = allCards[fieldId] ?? [];
    final updatedCards = fieldCards.map((c) {
      if (c.isCurrent) {
        return c.copyWith(isCurrent: false);
      }
      return c;
    }).toList();

    updatedCards.insert(0, savedCard.copyWith(isCurrent: true));
    allCards[fieldId] = updatedCards;

    await saveCards(allCards);
  }

  /// Saves the full map of Soil Health Cards to SharedPreferences local storage.
  Future<void> saveCards(Map<String, List<SoilHealthCard>> cards) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final Map<String, dynamic> jsonMap = {};
      for (final entry in cards.entries) {
        jsonMap[entry.key] = entry.value.map((c) => c.toJson()).toList();
      }
      await prefs.setString(_storageKey, jsonEncode(jsonMap));
    } catch (_) {}
  }

  /// Gets cards for a specific field.
  List<SoilHealthCard> getCardsForField(
    Map<String, List<SoilHealthCard>> allCards,
    String fieldId,
  ) {
    return allCards[fieldId] ?? [];
  }

  /// Gets the current card for a specific field.
  SoilHealthCard? getCurrentCardForField(
    Map<String, List<SoilHealthCard>> allCards,
    String fieldId,
  ) {
    final fieldCards = allCards[fieldId] ?? [];
    try {
      return fieldCards.firstWhere((c) => c.isCurrent);
    } catch (_) {
      return fieldCards.isNotEmpty ? fieldCards.first : null;
    }
  }

  /// Updates a specific card and persists.
  Future<void> updateCard(
    Map<String, List<SoilHealthCard>> allCards,
    String fieldId,
    SoilHealthCard updatedCard, {
    String? fid,
  }) async {
    final currentFid = fid ?? _supabase.auth.currentUser?.id ?? 'demo_farmer_id';
    final fieldCards = allCards[fieldId] ?? [];
    final index = fieldCards.indexWhere((c) => c.id == updatedCard.id);
    if (index != -1) {
      fieldCards[index] = updatedCard;
      allCards[fieldId] = fieldCards;

      try {
        final mapData = _soilHealthCardToMap(updatedCard);
        await _supabase.from('soil_health').update(mapData).eq('shid', updatedCard.id);
      } catch (e) {
        debugPrint('Error updating Soil Health Card in Supabase: $e');
      }

      await saveCards(allCards);
    }
  }

  /// Clears all saved Soil Health Card data.
  Future<void> clearAll() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_storageKey);
  }

  // --- Map Conversions ---
  static SoilHealthCard _soilHealthCardFromMap(Map<String, dynamic> json) {
    final idStr = (json['shid'] ?? json['SHID'] ?? json['id'] ?? '').toString();
    final fieldIdStr = (json['fieldid'] ?? json['FIELDID'] ?? json['field_id'] ?? json['fieldId'] ?? '').toString();

    double? numericValue(Object? value) {
      if (value is num) return value.toDouble();
      if (value is String) return double.tryParse(value);
      return null;
    }

    const nutrientColumns = <(String, String, String, String, NutrientCategory)>[
      ('ph', 'pH', '', 'normal', NutrientCategory.soilProperty),
      ('ec', 'EC', 'dS/m', 'normal', NutrientCategory.soilProperty),
      ('organic_carbon', 'Organic Carbon', '%', 'medium', NutrientCategory.soilProperty),
      ('nitrogen', 'Nitrogen (N)', 'kg/ha', 'medium', NutrientCategory.macronutrient),
      ('phosphorus', 'Phosphorus (P)', 'kg/ha', 'normal', NutrientCategory.macronutrient),
      ('potassium', 'Potassium (K)', 'kg/ha', 'normal', NutrientCategory.macronutrient),
      ('sulphur', 'Sulphur (S)', 'mg/kg', 'normal', NutrientCategory.secondaryNutrient),
      ('magnesium', 'Magnesium (Mg)', 'mg/kg', 'normal', NutrientCategory.secondaryNutrient),
      ('zinc', 'Zinc (Zn)', 'mg/kg', 'normal', NutrientCategory.micronutrient),
      ('iron', 'Iron (Fe)', 'mg/kg', 'normal', NutrientCategory.micronutrient),
      ('copper', 'Copper (Cu)', 'mg/kg', 'normal', NutrientCategory.micronutrient),
      ('boron', 'Boron (B)', 'mg/kg', 'normal', NutrientCategory.micronutrient),
    ];
    final nutrients = <SoilNutrientReading>[];
    for (final definition in nutrientColumns) {
      final (column, name, unit, status, category) = definition;
      final value = numericValue(json[column]);
      if (value == null) continue;
      nutrients.add(SoilNutrientReading(
        name: name,
        value: value,
        unit: unit,
        status: NutrientStatus.fromJson(status),
        category: category,
      ));
    }

    return SoilHealthCard(
      id: idStr.isNotEmpty ? idStr : 'shc_${DateTime.now().millisecondsSinceEpoch}',
      fieldId: fieldIdStr,
      cardNumber: json['card_number'] as String?,
      sampleId: json['sample_id'] as String?,
      farmerName: json['farmer_name'] as String?,
      fatherHusbandName: json['father_husband_name'] as String?,
      village: json['village'] as String?,
      tehsil: json['tehsil'] as String?,
      district: json['district'] as String?,
      state: json['state'] as String?,
      totalLandHolding: json['total_land_holding'] as String?,
      uploadDate: json['upload_date'] != null ? DateTime.tryParse(json['upload_date'].toString()) ?? DateTime.now() : DateTime.now(),
      soilType: json['soil_type'] as String?,
      soilColour: json['soil_colour'] as String?,
      soilTexture: json['soil_texture'] as String?,
      location: json['location'] as String?,
      nutrients: nutrients,
      fertilizerRecommendations: List<String>.from(json['fertilizer_recommendations'] as List? ?? []),
      nutrientRecommendations: List<String>.from(json['nutrient_recommendations'] as List? ?? []),
      cropRecommendations: List<String>.from(json['crop_recommendations'] as List? ?? []),
      sourceFileName: json['source_file_url'] ?? json['source_file_name'] as String?,
      isVerified: json['is_verified'] as bool? ?? true,
      isCurrent: json['is_current'] as bool? ?? true,
    );
  }

  static Map<String, dynamic> _soilHealthCardToMap(SoilHealthCard card) {
    SoilNutrientReading? getNut(String name) {
      try {
        return card.nutrients.firstWhere((n) => n.name.toLowerCase().contains(name.toLowerCase()));
      } catch (_) {
        return null;
      }
    }

    return {
      'fieldid': card.fieldId,
      'ph': getNut('pH')?.value,
      'ec': getNut('EC')?.value,
      'organic_carbon': getNut('Organic Carbon')?.value,
      'nitrogen': getNut('Nitrogen')?.value,
      'phosphorus': getNut('Phosphorus')?.value,
      'potassium': getNut('Potassium')?.value,
      'sulphur': getNut('Sulphur')?.value,
      'zinc': getNut('Zinc')?.value,
      'iron': getNut('Iron')?.value,
      'copper': getNut('Copper')?.value,
      'magnesium': getNut('Magnesium')?.value,
      'boron': getNut('Boron')?.value,
    };
  }

  Future<Map<String, List<SoilHealthCard>>> _loadLocalCards() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonString = prefs.getString(_storageKey);
      if (jsonString == null || jsonString.isEmpty) return {};
      final Map<String, dynamic> jsonMap = jsonDecode(jsonString) as Map<String, dynamic>;
      final Map<String, List<SoilHealthCard>> result = {};
      for (final entry in jsonMap.entries) {
        final List<dynamic> cardList = entry.value as List<dynamic>;
        result[entry.key] = cardList.map((item) => SoilHealthCard.fromJson(item as Map<String, dynamic>)).toList();
      }
      return result;
    } catch (_) {
      return {};
    }
  }
}
