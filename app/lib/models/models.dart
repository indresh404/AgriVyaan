class FarmerProfile {
  final String name;
  final String phone;
  final String email;
  final String preferredLanguage;
  final String location;
  final double farmArea;
  final String areaUnit; // acres or hectares
  final String mainCrop;
  final String? fid;

  FarmerProfile({
    required this.name,
    required this.phone,
    required this.email,
    required this.preferredLanguage,
    required this.location,
    required this.farmArea,
    required this.areaUnit,
    required this.mainCrop,
    this.fid,
  });

  factory FarmerProfile.fromMap(Map<String, dynamic> json) {
    return FarmerProfile(
      name: (json['name'] ?? json['Name'] ?? 'Farmer').toString(),
      phone: (json['phone_no'] ?? json['phone'] ?? json['Phone no'] ?? json['Phone'] ?? '').toString(),
      email: (json['email'] ?? 'farmer@agrivyaan.com').toString(),
      preferredLanguage: (json['preferred_language'] ?? json['preferredLanguage'] ?? 'en').toString(),
      location: (json['location'] ?? json['Location'] ?? 'Wardha, Maharashtra').toString(),
      farmArea: (json['farm_area'] ?? json['farmArea'] as num?)?.toDouble() ?? 5.0,
      areaUnit: (json['area_unit'] ?? json['areaUnit'] ?? 'acres').toString(),
      mainCrop: (json['main_crop'] ?? json['mainCrop'] ?? 'Cotton').toString(),
      fid: (json['fid'] ?? json['FID'] ?? json['auth_id'] ?? json['id'])?.toString(),
    );
  }

  Map<String, dynamic> toMap(String? authId) {
    // Only columns that exist in the public.users table: phone_no, name, location, auth_id
    final map = <String, dynamic>{
      'phone_no': phone,
      'name': name,
      'location': location.isNotEmpty ? location : null,
    };
    if (authId != null && authId.isNotEmpty) {
      map['auth_id'] = authId;
    }
    return map;
  }

  FarmerProfile copyWith({
    String? name,
    String? phone,
    String? email,
    String? preferredLanguage,
    String? location,
    double? farmArea,
    String? areaUnit,
    String? mainCrop,
    String? fid,
  }) {
    return FarmerProfile(
      name: name ?? this.name,
      phone: phone ?? this.phone,
      email: email ?? this.email,
      preferredLanguage: preferredLanguage ?? this.preferredLanguage,
      location: location ?? this.location,
      farmArea: farmArea ?? this.farmArea,
      areaUnit: areaUnit ?? this.areaUnit,
      mainCrop: mainCrop ?? this.mainCrop,
      fid: fid ?? this.fid,
    );
  }
}


class Zone {
  final String id;
  final String name;
  final String status; // Healthy, Low Moisture, Nutrient Stress, Risk, Disease Risk
  final double moisture; // percentage
  final double temperature; // celsius
  final String risk; // None, Low, Moderate, High
  final String aiExplanation;
  final String recommendation;

  Zone({
    required this.id,
    required this.name,
    required this.status,
    required this.moisture,
    required this.temperature,
    required this.risk,
    required this.aiExplanation,
    required this.recommendation,
  });

  Zone copyWith({
    String? status,
    double? moisture,
    double? temperature,
    String? risk,
    String? aiExplanation,
    String? recommendation,
  }) {
    return Zone(
      id: this.id,
      name: this.name,
      status: status ?? this.status,
      moisture: moisture ?? this.moisture,
      temperature: temperature ?? this.temperature,
      risk: risk ?? this.risk,
      aiExplanation: aiExplanation ?? this.aiExplanation,
      recommendation: recommendation ?? this.recommendation,
    );
  }
}

class SensorReading {
  final String sensorName;
  final double currentValue;
  final double minNormal;
  final double maxNormal;
  final String unit;
  final String status; // LOW, NORMAL, HIGH
  final List<double> history; // last 4 readings

  SensorReading({
    required this.sensorName,
    required this.currentValue,
    required this.minNormal,
    required this.maxNormal,
    required this.unit,
    required this.status,
    required this.history,
  });

  SensorReading copyWith({
    double? currentValue,
    String? status,
    List<double>? history,
  }) {
    return SensorReading(
      sensorName: this.sensorName,
      currentValue: currentValue ?? this.currentValue,
      minNormal: this.minNormal,
      maxNormal: this.maxNormal,
      unit: this.unit,
      status: status ?? this.status,
      history: history ?? this.history,
    );
  }
}

enum DroneScanStatus {
  requested,
  scheduled,
  droneAssigned,
  inProgress,
  processing,
  aiAnalysis,
  verification,
  reportReady,
  cancelled,
}

extension DroneScanStatusExtension on DroneScanStatus {
  String get displayName {
    switch (this) {
      case DroneScanStatus.requested:
        return 'REQUESTED';
      case DroneScanStatus.scheduled:
        return 'SCHEDULED';
      case DroneScanStatus.droneAssigned:
        return 'DRONE ASSIGNED';
      case DroneScanStatus.inProgress:
        return 'IN PROGRESS';
      case DroneScanStatus.processing:
        return 'PROCESSING';
      case DroneScanStatus.aiAnalysis:
        return 'AI ANALYSIS';
      case DroneScanStatus.verification:
        return 'VERIFICATION';
      case DroneScanStatus.reportReady:
        return 'REPORT READY';
      case DroneScanStatus.cancelled:
        return 'CANCELLED';
    }
  }
}

class DroneScan {
  final String id;
  final String? fid;
  final String fieldId;
  final String? fieldName;
  final DateTime? bookingDatetime;
  final DateTime? createdAt;
  final String scanType; // Crop Health Scan, Moisture/Soil Scan, Full Field Analysis
  final String date;
  final String time;
  final String operatorName;
  final DroneScanStatus status;
  final String verificationStatus; // PENDING, UNDER REVIEW, VERIFIED, REQUIRES REVIEW
  final int healthScore;
  final Map<String, dynamic>? aiReportData;

  DroneScan({
    required this.id,
    this.fid,
    required this.fieldId,
    this.fieldName,
    this.bookingDatetime,
    this.createdAt,
    required this.scanType,
    required this.date,
    required this.time,
    required this.operatorName,
    required this.status,
    required this.verificationStatus,
    this.healthScore = 80,
    this.aiReportData,
  });

  DroneScan copyWith({
    String? id,
    String? fid,
    String? fieldId,
    String? fieldName,
    DateTime? bookingDatetime,
    DateTime? createdAt,
    String? scanType,
    String? date,
    String? time,
    DroneScanStatus? status,
    String? verificationStatus,
    int? healthScore,
    Map<String, dynamic>? aiReportData,
    String? operatorName,
  }) {
    return DroneScan(
      id: id ?? this.id,
      fid: fid ?? this.fid,
      fieldId: fieldId ?? this.fieldId,
      fieldName: fieldName ?? this.fieldName,
      bookingDatetime: bookingDatetime ?? this.bookingDatetime,
      createdAt: createdAt ?? this.createdAt,
      scanType: scanType ?? this.scanType,
      date: date ?? this.date,
      time: time ?? this.time,
      operatorName: operatorName ?? this.operatorName,
      status: status ?? this.status,
      verificationStatus: verificationStatus ?? this.verificationStatus,
      healthScore: healthScore ?? this.healthScore,
      aiReportData: aiReportData ?? this.aiReportData,
    );
  }

  bool canCancelAt(DateTime now) {
    final bookedAt = createdAt;
    if (bookedAt == null ||
        (status != DroneScanStatus.requested &&
            status != DroneScanStatus.scheduled &&
            status != DroneScanStatus.droneAssigned)) {
      return false;
    }

    final elapsed = now.toUtc().difference(bookedAt.toUtc());
    return !elapsed.isNegative && elapsed < const Duration(hours: 8);
  }
}

class CropField {
  final String id;
  final String name;
  final int fieldNumber;
  final String? userName;
  final String crop;
  final double area;
  final String areaUnit;
  final double latitude;
  final double longitude;
  final String sowingDate;
  final String cropStage; // Germination, Vegetative, Flowering, Fruiting, Harvest
  final int healthScore;
  final int prevHealthScore;
  final String lastScanDate;
  final String moistureStatus; // LOW, NORMAL, HIGH
  final List<Zone> zones;
  final List<SensorReading> sensors;
  final List<String> activeAlerts;
  final String? location; // e.g. 'Lat: 20.7453, Long: 78.6022'

  CropField({
    required this.id,
    required this.name,
    this.fieldNumber = 1,
    this.userName,
    required this.crop,
    required this.area,
    required this.areaUnit,
    this.latitude = 20.7453,
    this.longitude = 78.6022,
    required this.sowingDate,
    required this.cropStage,
    required this.healthScore,
    required this.prevHealthScore,
    required this.lastScanDate,
    required this.moistureStatus,
    required this.zones,
    required this.sensors,
    required this.activeAlerts,
    this.location,
  });

  factory CropField.fromFarmField(dynamic f) {
    try {
      final zonesList = (f.zones as List?)?.map((z) {
        final riskString = z.severity ?? 'None';
        return Zone(
          id: 'z_${z.name.replaceAll(' ', '_')}',
          name: z.name as String,
          status: z.problem ?? 'Healthy',
          moisture: (z.soilMoisture as num).toDouble(),
          temperature: (z.temperature as num).toDouble(),
          risk: riskString.isNotEmpty ? riskString : 'None',
          aiExplanation: z.problem != null ? 'Issue detected: ${z.problem}' : 'Field conditions are within normal limits.',
          recommendation: z.recommendation ?? 'Monitor regularly.',
        );
      }).toList() ?? [];

      final alertsList = (f.problems as List?)?.map((p) => p.title as String).toList() ?? [];

      final moistureSensor = SensorReading(
        sensorName: 'Soil Moisture',
        currentValue: f.soilMoisture,
        minNormal: 35.0,
        maxNormal: 65.0,
        unit: '%',
        status: f.soilMoisture < 35 ? 'LOW' : 'NORMAL',
        history: [f.soilMoisture + 10, f.soilMoisture + 5, f.soilMoisture],
      );

      final tempSensor = SensorReading(
        sensorName: 'Temperature',
        currentValue: f.temperature,
        minNormal: 20.0,
        maxNormal: 35.0,
        unit: '°C',
        status: f.temperature > 35 ? 'HIGH' : 'NORMAL',
        history: [f.temperature - 2, f.temperature - 1, f.temperature],
      );

      final humiditySensor = SensorReading(
        sensorName: 'Humidity',
        currentValue: f.humidity,
        minNormal: 50.0,
        maxNormal: 80.0,
        unit: '%',
        status: 'NORMAL',
        history: [f.humidity - 5, f.humidity - 2, f.humidity],
      );

      final latVal = (f.latitude as num?)?.toDouble() ?? 20.7453;
      final lngVal = (f.longitude as num?)?.toDouble() ?? 78.6022;

      return CropField(
        id: f.id as String,
        name: f.name as String,
        fieldNumber: (f.fieldNumber as int?) ?? 1,
        userName: f.userName as String?,
        crop: f.crop as String,
        area: (f.area as num).toDouble(),
        areaUnit: 'acres',
        latitude: latVal,
        longitude: lngVal,
        sowingDate: f.sowingDate.toString().split(' ').first,
        cropStage: 'Vegetative stage',
        healthScore: f.healthScore.toInt(),
        prevHealthScore: f.healthScore.toInt(),
        lastScanDate: f.lastScan.toString().split(' ').first,
        moistureStatus: f.soilMoisture < 35 ? 'LOW' : 'NORMAL',
        zones: zonesList,
        sensors: [moistureSensor, tempSensor, humiditySensor],
        activeAlerts: alertsList,
        location: f.location as String?,
      );
    } catch (_) {
      return CropField(
        id: f.id as String,
        name: f.name as String,
        fieldNumber: (f.fieldNumber as int?) ?? 1,
        userName: f.userName as String?,
        crop: f.crop as String,
        area: (f.area as num).toDouble(),
        areaUnit: 'acres',
        latitude: 20.7453,
        longitude: 78.6022,
        sowingDate: '2026-08-26',
        cropStage: 'Vegetative stage',
        healthScore: f.healthScore.toInt(),
        prevHealthScore: f.healthScore.toInt(),
        lastScanDate: 'None',
        moistureStatus: 'NORMAL',
        zones: [],
        sensors: [],
        activeAlerts: [],
      );
    }
  }

  CropField copyWith({
    String? id,
    String? name,
    int? fieldNumber,
    String? userName,
    String? crop,
    double? area,
    String? areaUnit,
    double? latitude,
    double? longitude,
    String? sowingDate,
    String? cropStage,
    int? healthScore,
    int? prevHealthScore,
    String? lastScanDate,
    String? moistureStatus,
    List<Zone>? zones,
    List<SensorReading>? sensors,
    List<String>? activeAlerts,
    String? location,
  }) {
    return CropField(
      id: id ?? this.id,
      name: name ?? this.name,
      fieldNumber: fieldNumber ?? this.fieldNumber,
      userName: userName ?? this.userName,
      crop: crop ?? this.crop,
      area: area ?? this.area,
      areaUnit: areaUnit ?? this.areaUnit,
      latitude: latitude ?? this.latitude,
      longitude: longitude ?? this.longitude,
      sowingDate: sowingDate ?? this.sowingDate,
      cropStage: cropStage ?? this.cropStage,
      healthScore: healthScore ?? this.healthScore,
      prevHealthScore: prevHealthScore ?? this.prevHealthScore,
      lastScanDate: lastScanDate ?? this.lastScanDate,
      moistureStatus: moistureStatus ?? this.moistureStatus,
      zones: zones ?? this.zones,
      sensors: sensors ?? this.sensors,
      activeAlerts: activeAlerts ?? this.activeAlerts,
      location: location ?? this.location,
    );
  }
}

class ActionEntry {
  final String id;
  final String fieldId;
  final String title; // e.g., Irrigation, Treatment, Fertilization
  final String category; // Water, Pest, Nutrient, General
  final String zoneName;
  final String date;
  final String notes;
  final bool isCompleted;
  final Map<String, String>? beforeState; // e.g. {"Moisture": "27%", "Stress": "HIGH"}
  final Map<String, String>? afterState;  // e.g. {"Moisture": "48%", "Stress": "LOW"}
  final String? photoUrl;

  ActionEntry({
    required this.id,
    required this.fieldId,
    required this.title,
    required this.category,
    required this.zoneName,
    required this.date,
    required this.notes,
    required this.isCompleted,
    this.beforeState,
    this.afterState,
    this.photoUrl,
  });

  ActionEntry copyWith({
    bool? isCompleted,
    String? notes,
    Map<String, String>? afterState,
    String? photoUrl,
  }) {
    return ActionEntry(
      id: this.id,
      fieldId: this.fieldId,
      title: this.title,
      category: this.category,
      zoneName: this.zoneName,
      date: this.date,
      notes: notes ?? this.notes,
      isCompleted: isCompleted ?? this.isCompleted,
      beforeState: this.beforeState,
      afterState: afterState ?? this.afterState,
      photoUrl: photoUrl ?? this.photoUrl,
    );
  }
}

class WeatherForecast {
  final String dayName;
  final String date;
  final double temperature; // celsius
  final double rainProbability; // percentage
  final double humidity; // percentage
  final double windSpeed; // km/h
  final String weatherCondition; // Sunny, Rainy, Cloudy, etc.
  final String sprayingCondition; // GOOD, MODERATE, AVOID
  final String aiSummary;
  final String bestWindow;

  WeatherForecast({
    required this.dayName,
    required this.date,
    required this.temperature,
    required this.rainProbability,
    required this.humidity,
    required this.windSpeed,
    required this.weatherCondition,
    required this.sprayingCondition,
    required this.aiSummary,
    required this.bestWindow,
  });
}

class LibraryItem {
  final String id;
  final String type; // Crop, Pest, Disease
  final String name;
  final String description;
  final List<String> details; // Dynamic facts
  final String symptoms;
  final String prevention;
  final String management;
  final List<String> affectedCrops;
  final String? imageUrl;

  LibraryItem({
    required this.id,
    required this.type,
    required this.name,
    required this.description,
    required this.details,
    this.symptoms = '',
    this.prevention = '',
    this.management = '',
    required this.affectedCrops,
    this.imageUrl,
  });
}

class NotificationItem {
  final String id;
  final String title;
  final String description;
  final String time;
  final bool isRead;
  final bool isCritical;

  NotificationItem({
    required this.id,
    required this.title,
    required this.description,
    required this.time,
    required this.isRead,
    required this.isCritical,
  });

  NotificationItem copyWith({bool? isRead}) {
    return NotificationItem(
      id: this.id,
      title: this.title,
      description: this.description,
      time: this.time,
      isRead: isRead ?? this.isRead,
      isCritical: this.isCritical,
    );
  }
}
