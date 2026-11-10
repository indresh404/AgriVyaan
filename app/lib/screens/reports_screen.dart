import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart';
import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import '../models/models.dart';
import '../services/app_state.dart';
import '../widgets/custom_widgets.dart';
import '../services/field_storage_service.dart';
import '../models/farm_field.dart';

class ReportsScreen extends StatefulWidget {
  const ReportsScreen({super.key});

  @override
  State<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends State<ReportsScreen> {
  static const MethodChannel _downloadsChannel =
      MethodChannel('com.example.app/downloads');

  CropField? _selectedField;
  final FieldStorageService _storageService = FieldStorageService();
  List<FarmField> _localFields = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadLocalFields();
  }

  Future<void> _loadLocalFields() async {
    try {
      final loaded = await _storageService.loadFields();
      setState(() {
        _localFields = loaded;
        _isLoading = false;
      });
    } catch (_) {
      setState(() {
        _isLoading = false;
      });
    }
  }

  List<CropField> _getCombinedFields(AppState appState) {
    final combinedMap = <String, CropField>{};

    for (final farmField in _localFields) {
      combinedMap[farmField.id] = CropField.fromFarmField(farmField);
    }

    for (final cropField in appState.fields) {
      combinedMap[cropField.id] = cropField;
    }

    return combinedMap.values.toList();
  }

  @override
  Widget build(BuildContext context) {
    final appState = AppStateProvider.of(context);
    final allFields = _getCombinedFields(appState);

    if (_selectedField != null) {
      return _buildReportDetailView(context, appState, _selectedField!);
    }

    return Scaffold(
      backgroundColor: Colors.grey.shade50,
      appBar: _buildTopNavBar(context),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Colors.green))
          : allFields.isEmpty
              ? const Center(
                  child: Text(
                    'No fields registered yet. Register a field to view analysis reports.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Colors.grey),
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16.0),
                  itemCount: allFields.length,
                  itemBuilder: (context, index) {
                    final field = allFields[index];
                    return Card(
                      elevation: 0,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                        side: BorderSide(color: Colors.grey.shade200),
                      ),
                  margin: const EdgeInsets.only(bottom: 16),
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                    leading: Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: Colors.green.shade50,
                        shape: BoxShape.circle,
                      ),
                      child: Icon(Icons.assessment, color: Colors.green.shade800),
                    ),
                    title: Text(
                      field.name,
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                    ),
                    subtitle: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SizedBox(height: 4),
                        Text('Crop: ${field.crop}  |  Area: ${field.area} ac'),
                        Text(
                          'Last Audit Date: ${field.lastScanDate == 'None' ? '26 Aug 2026' : field.lastScanDate}',
                          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                        ),
                      ],
                    ),
                    trailing: const Icon(Icons.arrow_forward_ios, size: 16, color: Colors.green),
                    onTap: () {
                      _showReportOptionsSheet(context, appState, field);
                    },
                  ),
                );
              },
            ),
    );
  }

  Widget _buildReportDetailView(BuildContext context, AppState appState, CropField field) {
    final reportDate = field.lastScanDate == 'None' ? '26 Aug 2026' : field.lastScanDate;
    final reportTitle = '${field.name} - Full Field Analysis (Approved)';

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        foregroundColor: Colors.black,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () {
            setState(() {
              _selectedField = null;
            });
          },
        ),
        title: Text(
          field.name,
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Header Info Card
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.green.shade50,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.check_circle, color: Colors.green.shade800, size: 12),
                            const SizedBox(width: 4),
                            Text(
                              'APPROVED',
                              style: TextStyle(
                                color: Colors.green.shade800,
                                fontWeight: FontWeight.bold,
                                fontSize: 10,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        reportDate,
                        style: TextStyle(color: Colors.grey.shade600, fontSize: 12, fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    reportTitle,
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
                  ),
                  Text(
                    'Crop Type: ${field.crop}  •  Field Area: ${field.area} ${field.areaUnit}',
                    style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
                  ),
                  const Divider(height: 24),

                  // 1. Summary details (Indicator Cards, Parameters, Problems summary, and tables)
                  _buildSummaryTab(field),
                  const Divider(height: 32),

                  // 2. Drone Scan Images Section
                  const Text(
                    'Drone Aerial imagery Scans',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Colors.black87),
                  ),
                  const SizedBox(height: 8),
                  _buildImagesTab(field),
                  const Divider(height: 32),

                  // 3. Trend Graphs Section
                  const Text(
                    'Field Analytics Trend Progress',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Colors.black87),
                  ),
                  const SizedBox(height: 12),
                  _buildGraphsTab(field),
                  const Divider(height: 32),

                  // 4. Detailed Advice/Recommendations Section
                  _buildRecommendationTab(field),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),

          // Bottom CTA Buttons
          Container(
            padding: const EdgeInsets.all(16.0),
            decoration: BoxDecoration(
              color: Colors.white,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.05),
                  offset: const Offset(0, -2),
                  blurRadius: 10,
                ),
              ],
            ),
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.print, color: Colors.green),
                    label: const Text('View Full Report', style: TextStyle(color: Colors.green)),
                    style: OutlinedButton.styleFrom(
                      side: const BorderSide(color: Colors.green, width: 1.5),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                    onPressed: () {
                      _showPrintableReport(context, appState, field);
                    },
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton.icon(
                    icon: const Icon(Icons.download, color: Colors.white),
                    label: const Text('Download Report', style: TextStyle(color: Colors.white)),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green.shade700,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                    onPressed: () {
                      _generateAndDownloadReport(context, field);
                    },
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryTab(CropField field) {
    final tempSensor = field.sensors.firstWhere(
      (s) => s.sensorName.toLowerCase().contains('temp') || s.sensorName.toLowerCase().contains('temperature'),
      orElse: () => SensorReading(sensorName: 'Temperature', currentValue: 28.0, minNormal: 20.0, maxNormal: 35.0, unit: '°C', status: 'NORMAL', history: [28.0]),
    );
    final humiditySensor = field.sensors.firstWhere(
      (s) => s.sensorName.toLowerCase().contains('humid') || s.sensorName.toLowerCase().contains('humidity'),
      orElse: () => SensorReading(sensorName: 'Humidity', currentValue: 60.0, minNormal: 50.0, maxNormal: 80.0, unit: '%', status: 'NORMAL', history: [60.0]),
    );
    final moistureSensor = field.sensors.firstWhere(
      (s) => s.sensorName.toLowerCase().contains('moist') || s.sensorName.toLowerCase().contains('moisture'),
      orElse: () => SensorReading(sensorName: 'Soil Moisture', currentValue: 50.0, minNormal: 35.0, maxNormal: 65.0, unit: '%', status: 'NORMAL', history: [50.0]),
    );

    final moistureLabel = '${moistureSensor.currentValue}% (${moistureSensor.status})';
    final stressLabel = field.moistureStatus == 'LOW' ? 'High' : 'Normal';
    
    final activeAlertsList = field.activeAlerts;
    final hasAlerts = activeAlertsList.isNotEmpty;
    final alertText = hasAlerts
        ? activeAlertsList.join('. ')
        : 'No critical problems found. Field crop health remains stable.';

    final recommendations = field.zones
        .where((z) => z.risk.toLowerCase() != 'none')
        .map((z) => '${z.name}: ${z.recommendation}')
        .join('\n');
    final adviceText = recommendations.isNotEmpty
        ? recommendations
        : 'Continue weekly inspection sweeps. No additional water treatments required at this stage.';
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Health Indicator Card
        Row(
          children: [
            Expanded(
              child: Card(
                elevation: 0,
                color: Colors.green.shade50.withValues(alpha: 0.5),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: BorderSide(color: Colors.green.shade100),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    children: [
                      const Text('CROP HEALTH', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.black54)),
                      const SizedBox(height: 12),
                      Stack(
                        alignment: Alignment.center,
                        children: [
                          SizedBox(
                            width: 60,
                            height: 60,
                            child: CircularProgressIndicator(
                              value: field.healthScore / 100.0,
                              backgroundColor: Colors.green.shade100,
                              valueColor: AlwaysStoppedAnimation<Color>(Colors.green.shade800),
                              strokeWidth: 6,
                            ),
                          ),
                          Text(
                            '${field.healthScore}',
                            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.green.shade800),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      const Text('INDEX SCORE', style: TextStyle(fontSize: 9, color: Colors.grey)),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Card(
                elevation: 0,
                color: Colors.blue.shade50.withValues(alpha: 0.5),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: BorderSide(color: Colors.blue.shade100),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    children: [
                      const Text('SOIL MOISTURE', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.black54)),
                      const SizedBox(height: 12),
                      Text(
                        moistureLabel,
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: field.moistureStatus == 'LOW' ? Colors.red : Colors.blue.shade800,
                        ),
                      ),
                      const SizedBox(height: 10),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: (moistureSensor.currentValue / 100.0).clamp(0.0, 1.0),
                          backgroundColor: Colors.blue.shade100,
                          valueColor: AlwaysStoppedAnimation<Color>(field.moistureStatus == 'LOW' ? Colors.red : Colors.blue.shade800),
                          minHeight: 6,
                        ),
                      ),
                      const SizedBox(height: 6),
                      const Text('TELEMETRY VALUE', style: TextStyle(fontSize: 9, color: Colors.grey)),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),

        // Parameter Specs Card
        Card(
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: BorderSide(color: Colors.grey.shade200),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              children: [
                _buildParameterRow(Icons.thermostat, tempSensor.sensorName, '${tempSensor.currentValue}${tempSensor.unit}', Colors.red),
                const Divider(),
                _buildParameterRow(Icons.cloud_queue, humiditySensor.sensorName, '${humiditySensor.currentValue}${humiditySensor.unit}', Colors.blue),
                const Divider(),
                _buildParameterRow(Icons.warning_amber_rounded, 'Crop Stress', stressLabel, Colors.orange),
              ],
            ),
          ),
        ),
        const SizedBox(height: 20),

        // Problems Found Card
        const Text(
          'Problems Found',
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
        ),
        const SizedBox(height: 8),
        Card(
          elevation: 0,
          color: hasAlerts ? Colors.red.shade50 : Colors.green.shade50,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(color: hasAlerts ? Colors.red.shade100 : Colors.green.shade100),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Row(
              children: [
                Icon(
                  hasAlerts ? Icons.error_outline : Icons.check_circle_outline,
                  color: hasAlerts ? Colors.red : Colors.green.shade800,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    alertText,
                    style: TextStyle(
                      color: hasAlerts ? Colors.red.shade900 : Colors.green.shade900,
                      fontWeight: FontWeight.bold,
                      fontSize: 13,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 20),

        // AI Summary Card
        const Text(
          'Recommendation Summary',
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
        ),
        const SizedBox(height: 8),
        Text(
          adviceText,
          style: const TextStyle(fontSize: 14, height: 1.4, color: Colors.black87),
        ),
        const SizedBox(height: 24),
        _buildZoneTable(field),
        const SizedBox(height: 24),
        _buildSensorTable(field),
      ],
    );
  }

  Widget _buildImagesTab(CropField field) {
    return GridView.count(
      padding: const EdgeInsets.symmetric(vertical: 10),
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      crossAxisSpacing: 16,
      mainAxisSpacing: 16,
      children: field.zones.map((zone) {
        final isProblem = zone.risk.toLowerCase() != 'none';
        return _buildImageMockCard(
          '${zone.name} Drone Scan',
          zone.status,
          isProblem ? Colors.red : Colors.green,
        );
      }).toList(),
    );
  }

  Widget _buildImageMockCard(String title, String status, Color statusColor) {
    return Card(
      elevation: 0,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: Colors.grey.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Container(
              color: Colors.green.shade50,
              width: double.infinity,
              child: Icon(Icons.photo, size: 36, color: Colors.green.shade300),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(10.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 11),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Container(
                      width: 6,
                      height: 6,
                      decoration: BoxDecoration(color: statusColor, shape: BoxShape.circle),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      status,
                      style: TextStyle(color: statusColor, fontSize: 10, fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              ],
            ),
          )
        ],
      ),
    );
  }

  Widget _buildGraphsTab(CropField field) {
    final healthHistory = [
      (field.prevHealthScore.toDouble() - 4).clamp(0.0, 100.0),
      (field.prevHealthScore.toDouble() - 2).clamp(0.0, 100.0),
      field.prevHealthScore.toDouble(),
      field.healthScore.toDouble(),
    ];
    
    final hasMoisture = field.sensors.any((s) => s.sensorName.toLowerCase().contains('moist') || s.sensorName.toLowerCase().contains('moisture'));
    final moistureSensor = hasMoisture
        ? field.sensors.firstWhere((s) => s.sensorName.toLowerCase().contains('moist') || s.sensorName.toLowerCase().contains('moisture'))
        : null;
    final moistureHistory = moistureSensor?.history ?? [50.0, 50.0, 50.0, 50.0];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        CustomTrendChart(
          values: healthHistory,
          labels: const ['Scan 1', 'Scan 2', 'Scan 3', 'Current'],
          title: 'Health Trend Progress',
          lineColor: Colors.green,
        ),
        const SizedBox(height: 24),
        CustomTrendChart(
          values: moistureHistory,
          labels: List.generate(moistureHistory.length, (i) => i == moistureHistory.length - 1 ? 'Current' : 'Scan ${i + 1}'),
          title: 'Soil Moisture Trend Index',
          lineColor: Colors.blue,
        ),
        const SizedBox(height: 12),
        const Text(
          '*Trends are compiled from drone telemetry and field moisture sensors.',
          style: TextStyle(fontSize: 10, color: Colors.grey),
          textAlign: TextAlign.center,
        )
      ],
    );
  }

  Widget _buildRecommendationTab(CropField field) {
    final recommendationZones = field.zones.where((z) => z.risk.toLowerCase() != 'none').toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text(
          'Identified Problems & Recommended Solutions',
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Colors.black87),
        ),
        const SizedBox(height: 16),
        if (recommendationZones.isEmpty)
          Card(
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
              side: BorderSide(color: Colors.grey.shade200),
            ),
            child: const Padding(
              padding: EdgeInsets.all(20.0),
              child: Column(
                children: [
                  Icon(Icons.check_circle_outline, color: Colors.green, size: 48),
                  SizedBox(height: 12),
                  Text(
                     'No Action Required',
                     style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                  SizedBox(height: 8),
                  Text(
                     'All zones are in healthy conditions. Continue routine monitoring.',
                     textAlign: TextAlign.center,
                     style: TextStyle(color: Colors.grey),
                  ),
                ],
              ),
            ),
          )
        else
          ...recommendationZones.map((zone) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 16.0),
              child: _buildProblemSolutionCard(
                'Problem: ${zone.status} in ${zone.name}',
                zone.aiExplanation,
                'Solution: Action Required',
                zone.recommendation,
                zone.risk.toLowerCase() == 'high' || zone.risk.toLowerCase() == 'moderate',
              ),
            );
          }).toList(),
      ],
    );
  }

  Widget _buildProblemSolutionCard(String probTitle, String probDesc, String solTitle, String solDesc, bool isCritical) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: isCritical ? Colors.red.shade200 : Colors.grey.shade200, width: 1.5),
      ),
      color: isCritical ? Colors.red.shade50.withOpacity(0.33) : Colors.white,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  isCritical ? Icons.error_outline : Icons.info_outline,
                  color: isCritical ? Colors.red : Colors.blue,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    probTitle,
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                      color: isCritical ? Colors.red.shade900 : Colors.blue.shade900,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(probDesc, style: const TextStyle(fontSize: 13, color: Colors.black87)),
            const Divider(height: 24),
            Row(
              children: [
                const Icon(Icons.check_circle_outline, color: Colors.green, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    solTitle,
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Colors.green.shade900),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(solDesc, style: const TextStyle(fontSize: 13, color: Colors.black87)),
          ],
        ),
      ),
    );
  }

  Widget _buildParameterRow(IconData icon, String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 20),
              const SizedBox(width: 12),
              Text(
                label,
                style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 14, color: Colors.black87),
              ),
            ],
          ),
          Text(
            value,
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
          ),
        ],
      ),
    );
  }

  void _showPrintableReport(BuildContext context, AppState appState, CropField field) {
    final reportDate = field.lastScanDate == 'None' ? '26 Aug 2026' : field.lastScanDate;

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Row(
            children: [
              Icon(Icons.print, color: Colors.green),
              SizedBox(width: 8),
              Expanded(
                child: Text('Print-Ready Audit Report', overflow: TextOverflow.ellipsis),
              ),
            ],
          ),
          content: SizedBox(
            width: double.maxFinite,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                const Text(
                  'AGRIVYAAN CROP INTELLIGENCE SERVICES',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11, color: Colors.grey),
                ),
                const Divider(),
                Text('Field Identifier: ${field.name}', style: const TextStyle(fontWeight: FontWeight.bold)),
                Text('Crop Cultivar: ${field.crop}'),
                Text('Date of Audit: $reportDate'),
                Text('Operator Status: Flight Approved & Completed'),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(8),
                  color: Colors.green.shade50,
                  child: Text(
                    'Audit Summary Findings:\n• Health Metric: ${field.healthScore}/100\n• Water Index: ${field.moistureStatus}\n• Drone verification completed with zero exceptions.',
                    style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
                  ),
                ),
                const SizedBox(height: 12),
                const Text('Authorized Agronomist Signature:', style: TextStyle(fontSize: 11)),
                const SizedBox(height: 6),
                const Text(
                  'Dr. S. K. Sharma, Agritech Lead',
                  style: TextStyle(fontStyle: FontStyle.italic, fontWeight: FontWeight.bold, fontSize: 12),
                ),
              ],
            ),
          ),
        ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Document successfully sent to system print spooler.')),
                );
              },
              style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
              child: const Text('Print / Export PDF', style: TextStyle(color: Colors.white)),
            ),
          ],
        );
      },
    );
  }

  void _showReportOptionsSheet(BuildContext context, AppState appState, CropField field) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (BuildContext context) {
        return Container(
          padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: Colors.green.shade50,
                      shape: BoxShape.circle,
                    ),
                    child: Icon(Icons.assessment, color: Colors.green.shade800, size: 24),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          field.name,
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 18,
                          ),
                        ),
                        Text(
                          '${field.crop} • ${field.area} ac',
                          style: TextStyle(
                            color: Colors.grey.shade600,
                            fontSize: 14,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(context),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              ListTile(
                contentPadding: const EdgeInsets.symmetric(horizontal: 8),
                leading: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.blue.shade50,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(Icons.analytics_outlined, color: Colors.blue.shade800),
                ),
                title: const Text(
                  'View Full Report',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
                subtitle: const Text('Interactive graphs, zone-by-zone table, and advice'),
                trailing: const Icon(Icons.arrow_forward_ios, size: 14),
                onTap: () {
                  Navigator.pop(context);
                  setState(() {
                    _selectedField = field;
                  });
                },
              ),
              const Divider(height: 24),
              ListTile(
                contentPadding: const EdgeInsets.symmetric(horizontal: 8),
                leading: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.orange.shade50,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(Icons.file_download_outlined, color: Colors.orange.shade800),
                ),
                title: const Text(
                  'Download Report',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
                subtitle: const Text('Export crop analysis tables & graphs to your device'),
                trailing: const Icon(Icons.arrow_forward_ios, size: 14),
                onTap: () {
                  Navigator.pop(context);
                  _generateAndDownloadReport(context, field);
                },
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildZoneTable(CropField field) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: Colors.grey.shade200),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.layers, color: Colors.green, size: 20),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Zone Condition Table',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Table(
              columnWidths: const {
                0: FlexColumnWidth(1.2),
                1: FlexColumnWidth(1.8),
                2: FlexColumnWidth(1.1),
                3: FlexColumnWidth(1.0),
                4: FlexColumnWidth(1.0),
              },
              defaultVerticalAlignment: TableCellVerticalAlignment.middle,
              children: [
                TableRow(
                  decoration: BoxDecoration(
                    color: Colors.green.shade50,
                    borderRadius: const BorderRadius.vertical(top: Radius.circular(8)),
                  ),
                  children: const [
                    Padding(padding: EdgeInsets.all(8.0), child: Text('Zone', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.green, fontSize: 12))),
                    Padding(padding: EdgeInsets.all(8.0), child: Text('Status', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.green, fontSize: 12))),
                    Padding(padding: EdgeInsets.all(8.0), child: Text('Moist.', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.green, fontSize: 12))),
                    Padding(padding: EdgeInsets.all(8.0), child: Text('Temp', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.green, fontSize: 12))),
                    Padding(padding: EdgeInsets.all(8.0), child: Text('Risk', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.green, fontSize: 12))),
                  ],
                ),
                ...field.zones.map((zone) {
                  final isLowMoisture = zone.status.toLowerCase().contains('low moisture');
                  return TableRow(
                    decoration: BoxDecoration(
                      border: Border(bottom: BorderSide(color: Colors.grey.shade100)),
                    ),
                    children: [
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 4.0),
                        child: Text(
                          zone.name,
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 4.0),
                        child: Text(
                          zone.status,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: isLowMoisture ? Colors.red.shade900 : Colors.green.shade900,
                            fontWeight: FontWeight.bold,
                            fontSize: 10,
                          ),
                        ),
                      ),
                      Padding(padding: const EdgeInsets.all(8.0), child: Text('${zone.moisture}%', style: const TextStyle(fontSize: 12))),
                      Padding(padding: const EdgeInsets.all(8.0), child: Text('${zone.temperature}°C', style: const TextStyle(fontSize: 12))),
                      Padding(
                        padding: const EdgeInsets.all(8.0),
                        child: Text(
                          zone.risk,
                          style: TextStyle(
                            color: zone.risk.toLowerCase() == 'none' ? Colors.green : Colors.orange,
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  );
                }),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSensorTable(CropField field) {
    if (field.sensors.isEmpty) return const SizedBox.shrink();
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: Colors.grey.shade200),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.sensors, color: Colors.blue, size: 20),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Sensor Telemetry Table',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Table(
              columnWidths: const {
                0: FlexColumnWidth(1.8), // Sensor
                1: FlexColumnWidth(1.2), // Value
                2: FlexColumnWidth(1.5), // Range
                3: FlexColumnWidth(1.2), // Status
              },
              defaultVerticalAlignment: TableCellVerticalAlignment.middle,
              children: [
                TableRow(
                  decoration: BoxDecoration(
                    color: Colors.blue.shade50,
                    borderRadius: const BorderRadius.vertical(top: Radius.circular(8)),
                  ),
                  children: const [
                    Padding(padding: EdgeInsets.all(8.0), child: Text('Sensor', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.blue, fontSize: 12))),
                    Padding(padding: EdgeInsets.all(8.0), child: Text('Value', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.blue, fontSize: 12))),
                    Padding(padding: EdgeInsets.all(8.0), child: Text('Range', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.blue, fontSize: 12))),
                    Padding(padding: EdgeInsets.all(8.0), child: Text('Status', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.blue, fontSize: 12))),
                  ],
                ),
                ...field.sensors.map((sensor) {
                  final isLow = sensor.status == 'LOW';
                  return TableRow(
                    decoration: BoxDecoration(
                      border: Border(bottom: BorderSide(color: Colors.grey.shade100)),
                    ),
                    children: [
                      Padding(padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 4.0), child: Text(sensor.sensorName, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12))),
                      Padding(padding: const EdgeInsets.all(8.0), child: Text('${sensor.currentValue}${sensor.unit}', style: const TextStyle(fontSize: 12))),
                      Padding(padding: const EdgeInsets.all(8.0), child: Text('${sensor.minNormal}-${sensor.maxNormal}${sensor.unit}', style: const TextStyle(fontSize: 12))),
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 4.0),
                        child: Align(
                          alignment: Alignment.centerLeft,
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                            decoration: BoxDecoration(
                              color: isLow ? Colors.red.shade50 : Colors.green.shade50,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              sensor.status,
                              style: TextStyle(
                                color: isLow ? Colors.red.shade900 : Colors.green.shade900,
                                fontWeight: FontWeight.bold,
                                fontSize: 10,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  );
                }),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _generateAndDownloadReport(BuildContext context, CropField field) async {
    try {
      final pdf = pw.Document();
      final reportDate = field.lastScanDate == 'None' ? '26 Aug 2026' : field.lastScanDate;

      final moistureSensor = field.sensors.firstWhere(
        (s) => s.sensorName.toLowerCase().contains('moist') || s.sensorName.toLowerCase().contains('moisture'),
        orElse: () => SensorReading(sensorName: 'Soil Moisture', currentValue: 50.0, minNormal: 35.0, maxNormal: 65.0, unit: '%', status: 'NORMAL', history: [50.0]),
      );

      final activeAlertsList = field.activeAlerts;
      final hasAlerts = activeAlertsList.isNotEmpty;
      final alertText = hasAlerts
          ? activeAlertsList.join('. ')
          : 'No critical problems found. Field crop health remains stable.';
      final soilHealthCard =
          AppStateProvider.of(context).getCurrentCardForField(field.id);

      pdf.addPage(
        pw.MultiPage(
          pageFormat: PdfPageFormat.a4,
          margin: const pw.EdgeInsets.all(32),
          build: (pw.Context context) {
            return [
              pw.Text(
                'AGRIVYAAN CROP INTELLIGENCE REPORT',
                style: pw.TextStyle(fontSize: 18, fontWeight: pw.FontWeight.bold, color: PdfColors.green900),
              ),
              pw.SizedBox(height: 4),
              pw.Text(
                'Report Date: $reportDate | Field: ${field.name}',
                style: const pw.TextStyle(fontSize: 9, color: PdfColors.grey600),
              ),
              pw.SizedBox(height: 6),
              pw.Divider(thickness: 1.5, color: PdfColors.green800),
              pw.SizedBox(height: 12),

              pw.Text('FIELD SPECIFICATIONS', style: pw.TextStyle(fontSize: 11, fontWeight: pw.FontWeight.bold, color: PdfColors.green800)),
              pw.SizedBox(height: 6),
              pw.Table(
                border: pw.TableBorder.all(color: PdfColors.grey300),
                children: [
                  pw.TableRow(
                    children: [
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Crop Cultivar:', style: pw.TextStyle(fontSize: 10, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text(field.crop, style: const pw.TextStyle(fontSize: 10))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Field Area:', style: pw.TextStyle(fontSize: 10, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('${field.area} ${field.areaUnit}', style: const pw.TextStyle(fontSize: 10))),
                    ],
                  ),
                  pw.TableRow(
                    children: [
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Sowing Date:', style: pw.TextStyle(fontSize: 10, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text(field.sowingDate, style: const pw.TextStyle(fontSize: 10))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Growth Stage:', style: pw.TextStyle(fontSize: 10, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text(field.cropStage, style: const pw.TextStyle(fontSize: 10))),
                    ],
                  ),
                ],
              ),
              pw.SizedBox(height: 16),

              pw.Text(
                'SOIL HEALTH CARD LAB RESULTS',
                style: pw.TextStyle(
                  fontSize: 11,
                  fontWeight: pw.FontWeight.bold,
                  color: PdfColors.green800,
                ),
              ),
              pw.SizedBox(height: 6),
              if (soilHealthCard == null || soilHealthCard.nutrients.isEmpty)
                pw.Text(
                  'No Soil Health Card values have been saved for this field.',
                  style: const pw.TextStyle(fontSize: 9, color: PdfColors.grey700),
                )
              else
                pw.Table(
                  border: pw.TableBorder.all(color: PdfColors.grey300),
                  children: [
                    pw.TableRow(
                      decoration: const pw.BoxDecoration(color: PdfColors.green50),
                      children: [
                        for (final label in ['Parameter', 'Result', 'Unit'])
                          pw.Padding(
                            padding: const pw.EdgeInsets.all(6),
                            child: pw.Text(
                              label,
                              style: pw.TextStyle(
                                fontSize: 9,
                                fontWeight: pw.FontWeight.bold,
                              ),
                            ),
                          ),
                      ],
                    ),
                    ...soilHealthCard.nutrients.map((reading) {
                      return pw.TableRow(
                        children: [
                          pw.Padding(
                            padding: const pw.EdgeInsets.all(6),
                            child: pw.Text(reading.name,
                                style: const pw.TextStyle(fontSize: 9)),
                          ),
                          pw.Padding(
                            padding: const pw.EdgeInsets.all(6),
                            child: pw.Text(reading.value.toString(),
                                style: const pw.TextStyle(fontSize: 9)),
                          ),
                          pw.Padding(
                            padding: const pw.EdgeInsets.all(6),
                            child: pw.Text(reading.unit,
                                style: const pw.TextStyle(fontSize: 9)),
                          ),
                        ],
                      );
                    }),
                  ],
                ),
              pw.SizedBox(height: 16),

              pw.Row(
                children: [
                  pw.Expanded(
                    child: pw.Container(
                      padding: const pw.EdgeInsets.all(10),
                      decoration: pw.BoxDecoration(
                        color: PdfColors.green50,
                        border: pw.Border.all(color: PdfColors.green200),
                        borderRadius: const pw.BorderRadius.all(pw.Radius.circular(6)),
                      ),
                      child: pw.Column(
                        crossAxisAlignment: pw.CrossAxisAlignment.start,
                        children: [
                          pw.Text('CROP HEALTH SCORE', style: pw.TextStyle(fontSize: 8, fontWeight: pw.FontWeight.bold, color: PdfColors.green700)),
                          pw.SizedBox(height: 4),
                          pw.Text('${field.healthScore} / 100', style: pw.TextStyle(fontSize: 16, fontWeight: pw.FontWeight.bold, color: PdfColors.green900)),
                          pw.SizedBox(height: 6),
                          pw.Container(
                            height: 6,
                            decoration: const pw.BoxDecoration(
                              color: PdfColors.grey200,
                              borderRadius: pw.BorderRadius.all(pw.Radius.circular(3)),
                            ),
                            child: pw.Row(
                              children: [
                                pw.Expanded(
                                  flex: field.healthScore,
                                  child: pw.Container(
                                    height: 6,
                                    decoration: const pw.BoxDecoration(
                                      color: PdfColors.green800,
                                      borderRadius: pw.BorderRadius.all(pw.Radius.circular(3)),
                                    ),
                                  ),
                                ),
                                pw.Expanded(
                                  flex: (100 - field.healthScore).clamp(1, 100),
                                  child: pw.SizedBox(),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  pw.SizedBox(width: 12),
                  pw.Expanded(
                    child: pw.Container(
                      padding: const pw.EdgeInsets.all(10),
                      decoration: pw.BoxDecoration(
                        color: PdfColors.blue50,
                        border: pw.Border.all(color: PdfColors.blue200),
                        borderRadius: const pw.BorderRadius.all(pw.Radius.circular(6)),
                      ),
                      child: pw.Column(
                        crossAxisAlignment: pw.CrossAxisAlignment.start,
                        children: [
                          pw.Text('SOIL MOISTURE STATUS', style: pw.TextStyle(fontSize: 8, fontWeight: pw.FontWeight.bold, color: PdfColors.blue700)),
                          pw.SizedBox(height: 4),
                          pw.Text('${moistureSensor.currentValue}% (${moistureSensor.status})', style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold, color: PdfColors.blue900)),
                          pw.SizedBox(height: 6),
                          pw.Container(
                            height: 6,
                            decoration: const pw.BoxDecoration(
                              color: PdfColors.grey200,
                              borderRadius: pw.BorderRadius.all(pw.Radius.circular(3)),
                            ),
                            child: pw.Row(
                              children: [
                                pw.Expanded(
                                  flex: moistureSensor.currentValue.toInt().clamp(0, 100),
                                  child: pw.Container(
                                    height: 6,
                                    decoration: pw.BoxDecoration(
                                      color: field.moistureStatus == 'LOW' ? PdfColors.red800 : PdfColors.blue800,
                                      borderRadius: const pw.BorderRadius.all(pw.Radius.circular(3)),
                                    ),
                                  ),
                                ),
                                pw.Expanded(
                                  flex: (100 - moistureSensor.currentValue.toInt()).clamp(1, 100),
                                  child: pw.SizedBox(),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              pw.SizedBox(height: 16),

              pw.Container(
                padding: const pw.EdgeInsets.all(8),
                decoration: pw.BoxDecoration(
                  color: hasAlerts ? PdfColors.red50 : PdfColors.green50,
                  border: pw.Border.all(color: hasAlerts ? PdfColors.red200 : PdfColors.green200),
                  borderRadius: const pw.BorderRadius.all(pw.Radius.circular(6)),
                ),
                width: double.infinity,
                child: pw.Text(
                  'Audit Findings: $alertText',
                  style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold, color: hasAlerts ? PdfColors.red900 : PdfColors.green900),
                ),
              ),
              pw.SizedBox(height: 16),

              pw.Text('ZONE CONDITION ANALYSIS', style: pw.TextStyle(fontSize: 11, fontWeight: pw.FontWeight.bold, color: PdfColors.green800)),
              pw.SizedBox(height: 6),
              pw.Table(
                border: pw.TableBorder.all(color: PdfColors.grey300),
                children: [
                  pw.TableRow(
                    decoration: const pw.BoxDecoration(color: PdfColors.green50),
                    children: [
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Zone', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Status', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Moisture', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Temperature', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Risk', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                    ],
                  ),
                  ...field.zones.map((zone) {
                    return pw.TableRow(
                      children: [
                        pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text(zone.name, style: const pw.TextStyle(fontSize: 9))),
                        pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text(zone.status, style: const pw.TextStyle(fontSize: 9))),
                        pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('${zone.moisture}%', style: const pw.TextStyle(fontSize: 9))),
                        pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('${zone.temperature}°C', style: const pw.TextStyle(fontSize: 9))),
                        pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text(zone.risk, style: const pw.TextStyle(fontSize: 9))),
                      ],
                    );
                  }),
                ],
              ),
              pw.SizedBox(height: 16),

              pw.Text('SENSOR TELEMETRY READINGS', style: pw.TextStyle(fontSize: 11, fontWeight: pw.FontWeight.bold, color: PdfColors.blue800)),
              pw.SizedBox(height: 6),
              pw.Table(
                border: pw.TableBorder.all(color: PdfColors.grey300),
                children: [
                  pw.TableRow(
                    decoration: const pw.BoxDecoration(color: PdfColors.blue50),
                    children: [
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Sensor', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Value', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Normal Range', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Status', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                    ],
                  ),
                  ...field.sensors.map((sensor) {
                    return pw.TableRow(
                      children: [
                        pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text(sensor.sensorName, style: const pw.TextStyle(fontSize: 9))),
                        pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('${sensor.currentValue}${sensor.unit}', style: const pw.TextStyle(fontSize: 9))),
                        pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('${sensor.minNormal}-${sensor.maxNormal}${sensor.unit}', style: const pw.TextStyle(fontSize: 9))),
                        pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text(sensor.status, style: const pw.TextStyle(fontSize: 9))),
                      ],
                    );
                  }),
                ],
              ),
              pw.SizedBox(height: 16),

              pw.Text('DRONE IMAGERY SURVEY LOGS', style: pw.TextStyle(fontSize: 11, fontWeight: pw.FontWeight.bold, color: PdfColors.green800)),
              pw.SizedBox(height: 6),
              pw.Table(
                border: pw.TableBorder.all(color: PdfColors.grey300),
                children: [
                  pw.TableRow(
                    decoration: const pw.BoxDecoration(color: PdfColors.green50),
                    children: [
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Aerial Image Scan Label', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Covered Zone', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Vegetation Assessment', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                    ],
                  ),
                  ...field.zones.map((zone) {
                    final isProblem = zone.risk.toLowerCase() != 'none';
                    return pw.TableRow(
                      children: [
                        pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('${zone.name} Drone Scan', style: const pw.TextStyle(fontSize: 9))),
                        pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text(zone.name, style: const pw.TextStyle(fontSize: 9))),
                        pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text(isProblem ? 'Warning: ${zone.status}' : 'Healthy: Optimal Leaf Area', style: const pw.TextStyle(fontSize: 9))),
                      ],
                    );
                  }),
                ],
              ),
              pw.SizedBox(height: 16),

              pw.Text('TELEMETRY INDEX TREND LINES', style: pw.TextStyle(fontSize: 11, fontWeight: pw.FontWeight.bold, color: PdfColors.blue800)),
              pw.SizedBox(height: 6),
              pw.Table(
                border: pw.TableBorder.all(color: PdfColors.grey300),
                children: [
                  pw.TableRow(
                    decoration: const pw.BoxDecoration(color: PdfColors.blue50),
                    children: [
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Telemetry Metric', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Scan 1', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Scan 2', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Scan 3', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Current Value', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
                    ],
                  ),
                  pw.TableRow(
                    children: [
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Crop Health Score', style: const pw.TextStyle(fontSize: 9))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('${(field.prevHealthScore - 4).clamp(0, 100)}', style: const pw.TextStyle(fontSize: 9))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('${(field.prevHealthScore - 2).clamp(0, 100)}', style: const pw.TextStyle(fontSize: 9))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('${field.prevHealthScore}', style: const pw.TextStyle(fontSize: 9))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('${field.healthScore}', style: const pw.TextStyle(fontSize: 9))),
                    ],
                  ),
                  pw.TableRow(
                    children: [
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('Soil Moisture (%)', style: const pw.TextStyle(fontSize: 9))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('${moistureSensor.history.isNotEmpty ? moistureSensor.history[0].round() : 50}%', style: const pw.TextStyle(fontSize: 9))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('${moistureSensor.history.length > 1 ? moistureSensor.history[1].round() : 50}%', style: const pw.TextStyle(fontSize: 9))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('${moistureSensor.history.length > 2 ? moistureSensor.history[2].round() : 50}%', style: const pw.TextStyle(fontSize: 9))),
                      pw.Padding(padding: const pw.EdgeInsets.all(6), child: pw.Text('${moistureSensor.currentValue.round()}%', style: const pw.TextStyle(fontSize: 9))),
                    ],
                  ),
                ],
              ),
              pw.SizedBox(height: 16),

              pw.Text('HISTORICAL ANALYTICS TREND PROGRESS (VISUAL CHARTS)', style: pw.TextStyle(fontSize: 11, fontWeight: pw.FontWeight.bold, color: PdfColors.green800)),
              pw.SizedBox(height: 8),
              pw.Row(
                mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
                children: [
                  // Chart 1: Crop Health Trend
                  pw.Expanded(
                    child: pw.Container(
                      padding: const pw.EdgeInsets.all(8),
                      decoration: pw.BoxDecoration(
                        border: pw.Border.all(color: PdfColors.grey300),
                        borderRadius: const pw.BorderRadius.all(pw.Radius.circular(6)),
                      ),
                      child: pw.Column(
                        crossAxisAlignment: pw.CrossAxisAlignment.start,
                        children: [
                          pw.Text('Crop Health Index History', style: pw.TextStyle(fontSize: 8, fontWeight: pw.FontWeight.bold, color: PdfColors.green800)),
                          pw.SizedBox(height: 12),
                          pw.Container(
                            height: 60,
                            child: pw.Row(
                              mainAxisAlignment: pw.MainAxisAlignment.spaceAround,
                              crossAxisAlignment: pw.CrossAxisAlignment.end,
                              children: [
                                _buildPdfBar('Scan 1', (field.prevHealthScore - 4).clamp(0, 100).toDouble(), PdfColors.green300),
                                _buildPdfBar('Scan 2', (field.prevHealthScore - 2).clamp(0, 100).toDouble(), PdfColors.green400),
                                _buildPdfBar('Scan 3', field.prevHealthScore.toDouble(), PdfColors.green600),
                                _buildPdfBar('Current', field.healthScore.toDouble(), PdfColors.green800),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  pw.SizedBox(width: 12),
                  // Chart 2: Soil Moisture Trend
                  pw.Expanded(
                    child: pw.Container(
                      padding: const pw.EdgeInsets.all(8),
                      decoration: pw.BoxDecoration(
                        border: pw.Border.all(color: PdfColors.grey300),
                        borderRadius: const pw.BorderRadius.all(pw.Radius.circular(6)),
                      ),
                      child: pw.Column(
                        crossAxisAlignment: pw.CrossAxisAlignment.start,
                        children: [
                          pw.Text('Soil Moisture (%) History', style: pw.TextStyle(fontSize: 8, fontWeight: pw.FontWeight.bold, color: PdfColors.blue800)),
                          pw.SizedBox(height: 12),
                          pw.Container(
                            height: 60,
                            child: pw.Row(
                              mainAxisAlignment: pw.MainAxisAlignment.spaceAround,
                              crossAxisAlignment: pw.CrossAxisAlignment.end,
                              children: [
                                _buildPdfBar('Scan 1', moistureSensor.history.isNotEmpty ? moistureSensor.history[0] : 50.0, PdfColors.blue300),
                                _buildPdfBar('Scan 2', moistureSensor.history.length > 1 ? moistureSensor.history[1] : 50.0, PdfColors.blue400),
                                _buildPdfBar('Scan 3', moistureSensor.history.length > 2 ? moistureSensor.history[2] : 50.0, PdfColors.blue600),
                                _buildPdfBar('Current', moistureSensor.currentValue, PdfColors.blue800),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              pw.SizedBox(height: 16),

              pw.Text('EXPERT RECOMMENDATION & CROP SOLUTIONS', style: pw.TextStyle(fontSize: 11, fontWeight: pw.FontWeight.bold, color: PdfColors.green800)),
              pw.SizedBox(height: 6),
              ...field.zones.where((z) => z.risk.toLowerCase() != 'none').map((zone) {
                return pw.Container(
                  margin: const pw.EdgeInsets.only(bottom: 8),
                  padding: const pw.EdgeInsets.all(8),
                  decoration: pw.BoxDecoration(
                    color: PdfColors.grey100,
                    border: pw.Border.all(color: PdfColors.grey300),
                    borderRadius: const pw.BorderRadius.all(pw.Radius.circular(4)),
                  ),
                  child: pw.Column(
                    crossAxisAlignment: pw.CrossAxisAlignment.start,
                    children: [
                      pw.Text('Problem: ${zone.status} in ${zone.name}', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold, color: PdfColors.red900)),
                      pw.SizedBox(height: 2),
                      pw.Text('AI Assessment: ${zone.aiExplanation}', style: const pw.TextStyle(fontSize: 8)),
                      pw.SizedBox(height: 4),
                      pw.Text('Action Plan: ${zone.recommendation}', style: pw.TextStyle(fontSize: 8, fontWeight: pw.FontWeight.bold, color: PdfColors.green900)),
                    ],
                  ),
                );
              }).toList(),
              if (field.zones.where((z) => z.risk.toLowerCase() != 'none').isEmpty)
                pw.Padding(
                  padding: const pw.EdgeInsets.only(bottom: 8),
                  child: pw.Text('No critical zone actions are required. All indices represent healthy parameters.', style: const pw.TextStyle(fontSize: 9)),
                ),
              pw.SizedBox(height: 16),

              pw.Divider(thickness: 1, color: PdfColors.grey300),
              pw.Align(
                alignment: pw.Alignment.centerRight,
                child: pw.Text(
                  'Authorized Agritech Lead Signature: Dr. S. K. Sharma',
                  style: pw.TextStyle(fontSize: 7, fontStyle: pw.FontStyle.italic),
                ),
              ),
            ];
          },
        ),
      );

      final pdfBytes = await pdf.save();

      String filePath = '';
      File? file;
      bool savedDirectly = false;
      bool savedToDownloads = false;

      try {
        if (Platform.isAndroid) {
          final safeFieldName =
              field.name.replaceAll(RegExp(r'[^A-Za-z0-9_-]'), '_');
          final fileName = 'agrivyaan_report_$safeFieldName.pdf';
          await _downloadsChannel.invokeMethod<String>('savePdfToDownloads', {
            'fileName': fileName,
            'bytes': pdfBytes,
          });
          filePath = fileName;
          savedDirectly = true;
          savedToDownloads = true;
        } else if (Platform.isWindows) {
          final home = Platform.environment['USERPROFILE'];
          final winDownload = Directory('$home\\Downloads');
          filePath = '${winDownload.path}\\agrivyaan_report_${field.name.replaceAll(' ', '_')}.pdf';
          file = File(filePath);
          await file.writeAsBytes(pdfBytes);
          savedDirectly = true;
        } else if (Platform.isIOS) {
          final appDocs = await getApplicationDocumentsDirectory();
          filePath = '${appDocs.path}/agrivyaan_report_${field.name.replaceAll(' ', '_')}.pdf';
          file = File(filePath);
          await file.writeAsBytes(pdfBytes);
          savedDirectly = true;
        }
      } catch (e) {
        debugPrint('Direct write error: $e');
      }

      final tempDir = await getTemporaryDirectory();
      final tempFilePath = '${tempDir.path}/agrivyaan_report_${field.name.replaceAll(' ', '_')}.pdf';
      final tempFile = File(tempFilePath);
      await tempFile.writeAsBytes(pdfBytes);

      if (context.mounted) {
        showDialog(
          context: context,
          builder: (context) => AlertDialog(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            title: const Row(
              children: [
                Icon(Icons.download_done, color: Colors.green),
                SizedBox(width: 8),
                Expanded(
                  child: Text('PDF Report Generated', overflow: TextOverflow.ellipsis),
                ),
              ],
            ),
            content: SizedBox(
              width: double.maxFinite,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    savedToDownloads
                        ? 'The PDF report was successfully saved to your downloads folder as:\n'
                        : savedDirectly
                            ? 'The PDF report was saved on this device as:\n'
                            : 'PDF Report successfully generated!\n',
                    style: const TextStyle(fontSize: 13),
                  ),
                  if (savedDirectly) ...[
                    const SizedBox(height: 6),
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: Colors.grey.shade100,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.grey.shade300),
                      ),
                      width: double.infinity,
                      child: Text(
                        file?.path.split('/').last ?? filePath.split('/').last,
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: Colors.black87,
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'The report is saved locally. You can also share a copy.',
                      style: TextStyle(fontSize: 13),
                    ),
                  ] else ...[
                    const Text(
                      'Use the system menu to save it to your phone\'s Files or send it via chat/email.',
                      style: TextStyle(fontSize: 13),
                    ),
                  ],
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Close'),
              ),
              ElevatedButton.icon(
                icon: const Icon(Icons.share, color: Colors.white, size: 16),
                label: const Text('Share PDF', style: TextStyle(color: Colors.white)),
                style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
                onPressed: () async {
                  Navigator.pop(context);
                  await Share.shareXFiles(
                    [XFile(tempFilePath, mimeType: 'application/pdf')],
                    subject: 'Crop Report PDF - ${field.name}',
                  );
                },
              ),
            ],
          ),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to generate PDF report: $e')),
        );
      }
    }
  }

  PreferredSizeWidget _buildTopNavBar(BuildContext context) {
    return PreferredSize(
      preferredSize: const Size.fromHeight(85),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: Container(
            height: 65,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.08),
                  blurRadius: 10,
                  offset: const Offset(0, 4),
                ),
              ],
              border: Border.all(color: Colors.grey.shade100),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Icon(Icons.psychology, color: Colors.green.shade800, size: 28),
                      const SizedBox(width: 8),
                      const Text(
                        'Agrivyaan',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Colors.green),
                      ),
                    ],
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: Colors.green.shade50,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.assessment, color: Colors.green.shade800, size: 16),
                        const SizedBox(width: 6),
                        Text(
                          'Reports',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                            color: Colors.green.shade800,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  pw.Widget _buildPdfBar(String label, double value, PdfColor color) {
    final barHeight = 5.0 + (value.clamp(0, 100) / 100.0 * 40.0);
    return pw.Column(
      mainAxisAlignment: pw.MainAxisAlignment.end,
      children: [
        pw.Text('${value.round()}', style: const pw.TextStyle(fontSize: 6, color: PdfColors.grey700)),
        pw.SizedBox(height: 2),
        pw.Container(
          width: 14,
          height: barHeight,
          decoration: pw.BoxDecoration(
            color: color,
            borderRadius: const pw.BorderRadius.all(pw.Radius.circular(2)),
          ),
        ),
        pw.SizedBox(height: 4),
        pw.Text(label, style: const pw.TextStyle(fontSize: 6)),
      ],
    );
  }
}
