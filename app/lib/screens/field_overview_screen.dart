import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/farm_field.dart';
import '../services/app_state.dart';
import '../services/field_storage_service.dart';
import '../utils/app_theme.dart';
import '../utils/field_helpers.dart';
import '../widgets/health_indicator.dart';
import '../widgets/sensor_card.dart';
import '../widgets/problem_card.dart';
import '../widgets/improvement_card.dart';
import '../widgets/zone_card.dart';
import '../widgets/field_zone_map.dart';
import 'add_field_screen.dart';
import 'zone_details_screen.dart';
import '../widgets/custom_widgets.dart';

/// Comprehensive single-field view with health, sensors, zones, problems, and improvements.
class FieldOverviewScreen extends StatefulWidget {
  final FarmField field;
  final List<FarmField> fields;
  final FieldStorageService storageService;

  const FieldOverviewScreen({
    super.key,
    required this.field,
    required this.fields,
    required this.storageService,
  });

  @override
  State<FieldOverviewScreen> createState() => _FieldOverviewScreenState();
}

class _FieldOverviewScreenState extends State<FieldOverviewScreen> {
  late FarmField _field;

  @override
  void initState() {
    super.initState();
    _field = widget.field;
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 4,
      child: Scaffold(
        backgroundColor: AppTheme.scaffoldBackground,
        appBar: AppBar(
          backgroundColor: Colors.white,
          foregroundColor: AppTheme.textPrimary,
          elevation: 0.5,
          title: Text(
            _field.name,
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
          ),
          actions: [
            PopupMenuButton<String>(
              icon: const Icon(Icons.more_vert),
              onSelected: _handleMenuAction,
              itemBuilder: (context) => [
                const PopupMenuItem(
                  value: 'edit',
                  child: Row(
                    children: [
                      Icon(Icons.edit_outlined, size: 20),
                      SizedBox(width: 8),
                      Text('Edit Field'),
                    ],
                  ),
                ),
                const PopupMenuItem(
                  value: 'delete',
                  child: Row(
                    children: [
                      Icon(Icons.delete_outline, size: 20, color: AppTheme.error),
                      SizedBox(width: 8),
                      Text('Delete Field', style: TextStyle(color: AppTheme.error)),
                    ],
                  ),
                ),
              ],
            ),
          ],
          bottom: const TabBar(
            labelColor: AppTheme.primaryGreen,
            unselectedLabelColor: Colors.black54,
            indicatorColor: AppTheme.primaryGreen,
            isScrollable: false,
            labelStyle: TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
            unselectedLabelStyle: TextStyle(fontSize: 11),
            tabs: [
              Tab(text: 'Overview', icon: Icon(Icons.dashboard_outlined, size: 18)),
              Tab(text: 'Scans', icon: Icon(Icons.photo_library_outlined, size: 18)),
              Tab(text: 'Trends', icon: Icon(Icons.trending_up_rounded, size: 18)),
              Tab(text: 'Advice', icon: Icon(Icons.psychology_outlined, size: 18)),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _buildOverviewTab(),
            _buildDroneImagesTab(),
            _buildTrendGraphsTab(),
            _buildAdviceTab(),
          ],
        ),
      ),
    );
  }

  Widget _buildOverviewTab() {
    final moistureStatus = getMoistureStatus(_field.soilMoisture);
    final tempStatus = getTemperatureStatus(_field.temperature);
    final humidityStatus = getHumidityStatus(_field.humidity);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Field info summary
        _buildFieldInfo(),
        const SizedBox(height: 16),

        // Health score
        _buildSectionTitle('Crop Health Status', Icons.favorite_rounded),
        const SizedBox(height: 12),
        Center(child: HealthIndicator(score: _field.healthScore)),
        const SizedBox(height: 24),

        // Sensor readings
        _buildSectionTitle('Field Conditions', Icons.sensors_rounded),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: SensorCard(
                icon: Icons.water_drop_rounded,
                title: 'Soil Moisture',
                value: '${_field.soilMoisture.round()}',
                unit: '%',
                statusLabel: moistureStatusLabel(moistureStatus),
                statusColor: moistureStatusColor(moistureStatus),
                isDemoData: _field.isDemoData,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: SensorCard(
                icon: Icons.thermostat_rounded,
                title: 'Temperature',
                value: '${_field.temperature.round()}',
                unit: '°C',
                statusLabel: temperatureStatusLabel(tempStatus),
                statusColor: temperatureStatusColor(tempStatus),
                isDemoData: _field.isDemoData,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: SensorCard(
                icon: Icons.water_outlined,
                title: 'Humidity',
                value: '${_field.humidity.round()}',
                unit: '%',
                statusLabel: humidityStatusLabel(humidityStatus),
                statusColor: humidityStatusColor(humidityStatus),
                isDemoData: _field.isDemoData,
              ),
            ),
          ],
        ),

        // Sensor connection status
        if (_field.isDemoData) ...[
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: AppTheme.warning.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppTheme.warning.withValues(alpha: 0.2)),
            ),
            child: const Row(
              children: [
                Icon(Icons.info_outline, size: 16, color: AppTheme.warning),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Showing demo sensor values. Connect sensors or drones for live data.',
                    style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                  ),
                ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 24),

        // Field Zones
        if (_field.zones.isNotEmpty) ...[
          _buildSectionTitle('Field Zones Layout', Icons.grid_view_rounded),
          const SizedBox(height: 12),
          FieldZoneMap(
            zones: _field.zones,
            onZoneTap: _openZoneDetails,
          ),
          const SizedBox(height: 12),
          ..._field.zones.map(
            (zone) => ZoneCard(
              zone: zone,
              onTap: () => _openZoneDetails(zone),
            ),
          ),
          const SizedBox(height: 24),
        ],

        // Active Problems / If no problems
        if (_field.problems.isNotEmpty) ...[
          _buildSectionTitle(
              'Active Problems (${_field.problems.length})',
              Icons.warning_amber_rounded),
          const SizedBox(height: 12),
          ..._field.problems.map((p) => ProblemCard(problem: p)),
          const SizedBox(height: 24),
        ] else ...[
          _buildSectionTitle('Active Problems', Icons.warning_amber_rounded),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppTheme.primaryGreenSurface,
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Row(
              children: [
                Icon(Icons.check_circle_rounded, color: AppTheme.primaryGreen, size: 28),
                SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'No Problems Detected',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.primaryGreen,
                        ),
                      ),
                      SizedBox(height: 2),
                      Text(
                        'Your field is in good condition.',
                        style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
        ],

        // Improvements
        if (_field.improvements.isNotEmpty) ...[
          _buildSectionTitle('Improvements Needed', Icons.lightbulb_outline),
          const SizedBox(height: 12),
          ..._field.improvements.map((i) => ImprovementCard(improvement: i)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: AppTheme.info.withValues(alpha: 0.06),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Row(
              children: [
                Icon(Icons.smart_toy_outlined, size: 14, color: AppTheme.info),
                SizedBox(width: 6),
                Expanded(
                  child: Text(
                    'Recommendations are AI-assisted and should be verified when required.',
                    style: TextStyle(fontSize: 11, color: AppTheme.textSecondary, fontStyle: FontStyle.italic),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
        ],
      ],
    );
  }

  Widget _buildDroneImagesTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildSectionTitle('Drone Aerial Imagery Scans', Icons.photo_library_outlined),
        const SizedBox(height: 12),
        _buildImagesSection(),
      ],
    );
  }

  Widget _buildTrendGraphsTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildSectionTitle('Field Analytics Trend Progress', Icons.trending_up_rounded),
        const SizedBox(height: 12),
        _buildTrendChartsSection(),
      ],
    );
  }

  Widget _buildAdviceTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildSectionTitle('Detailed Advice & Solutions', Icons.psychology_outlined),
        const SizedBox(height: 12),
        _buildAdviceSection(),
      ],
    );
  }

  Widget _buildFieldInfo() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border, width: 0.5),
      ),
      child: Column(
        children: [
          _infoRow(Icons.agriculture, 'Crop', _field.crop),
          _infoDivider(),
          _infoRow(Icons.square_foot, 'Area', '${_field.area} acres'),
          _infoDivider(),
          _infoRow(Icons.location_on_outlined, 'Location', _field.location),
          _infoDivider(),
          _infoRow(Icons.calendar_today_outlined, 'Sowing Date',
              DateFormat('MMMM d, y').format(_field.sowingDate)),
          _infoDivider(),
          _infoRow(Icons.schedule_outlined, 'Last Scan',
              DateFormat('MMM d, y – h:mm a').format(_field.lastScan)),
          if (_field.notes != null && _field.notes!.isNotEmpty) ...[
            _infoDivider(),
            _infoRow(Icons.notes_outlined, 'Notes', _field.notes!),
          ],
        ],
      ),
    );
  }

  Widget _infoRow(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: AppTheme.textLight),
          const SizedBox(width: 10),
          SizedBox(
            width: 80,
            child: Text(
              label,
              style: const TextStyle(
                  fontSize: 13,
                  color: AppTheme.textSecondary,
                  fontWeight: FontWeight.w500),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
              overflow: TextOverflow.visible,
              softWrap: true,
            ),
          ),
        ],
      ),
    );
  }

  Widget _infoDivider() {
    return const Divider(height: 16, color: AppTheme.border);
  }

  Widget _buildSectionTitle(String title, IconData icon) {
    return Row(
      children: [
        Icon(icon, size: 20, color: AppTheme.primaryGreen),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            title,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }

  void _handleMenuAction(String action) {
    switch (action) {
      case 'edit':
        _editField();
        break;
      case 'delete':
        _confirmDelete();
        break;
    }
  }

  void _editField() async {
    final result = await Navigator.push<FarmField>(
      context,
      MaterialPageRoute(
        builder: (_) => AddFieldScreen(
          fields: widget.fields,
          storageService: widget.storageService,
          existingField: _field,
        ),
      ),
    );
    if (result != null) {
      // Reload the field from storage
      final updated = await widget.storageService.loadFields();
      final refreshed = updated.firstWhere(
        (f) => f.id == _field.id,
        orElse: () => _field,
      );
      setState(() => _field = refreshed);
    }
  }

  void _confirmDelete() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(Icons.warning_amber_rounded, color: AppTheme.error),
            SizedBox(width: 8),
            Text('Delete Field?'),
          ],
        ),
        content: Text(
          'Are you sure you want to remove "${_field.name}"? This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(ctx); // close dialog
              AppState? appState;
              try {
                appState = AppStateProvider.of(context);
              } catch (_) {}
              if (appState != null) {
                appState.deleteField(_field.id);
              } else {
                await widget.storageService
                    .deleteField(widget.fields, _field.id);
              }
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('${_field.name} deleted'),
                    backgroundColor: AppTheme.error,
                  ),
                );
                Navigator.pop(context); // back to list
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.error,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }

  void _openZoneDetails(FieldZone zone) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ZoneDetailsScreen(
          zone: zone,
          fieldName: _field.name,
        ),
      ),
    );
  }

  Widget _buildImagesSection() {
    return GridView.count(
      padding: const EdgeInsets.symmetric(vertical: 10),
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      crossAxisSpacing: 16,
      mainAxisSpacing: 16,
      children: _field.zones.map((zone) {
        final isProblem = zone.severity != null && zone.severity!.toLowerCase() != 'none';
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
                  child: const Icon(Icons.photo, size: 36, color: Colors.green),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(10.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${zone.name} Drone Scan',
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
                          decoration: BoxDecoration(
                            color: isProblem ? Colors.red : Colors.green,
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 4),
                        Text(
                          zone.problem ?? 'Healthy',
                          style: TextStyle(
                            color: isProblem ? Colors.red : Colors.green,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              )
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _buildTrendChartsSection() {
    final healthHistory = [
      (_field.healthScore - 4.0).clamp(0.0, 100.0),
      (_field.healthScore - 2.0).clamp(0.0, 100.0),
      _field.healthScore,
      _field.healthScore,
    ];
    final moistureHistory = [
      (_field.soilMoisture - 5.0).clamp(0.0, 100.0),
      (_field.soilMoisture + 2.0).clamp(0.0, 100.0),
      _field.soilMoisture,
      _field.soilMoisture,
    ];

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
          labels: const ['Scan 1', 'Scan 2', 'Scan 3', 'Current'],
          title: 'Soil Moisture Trend Index',
          lineColor: Colors.blue,
        ),
      ],
    );
  }

  Widget _buildAdviceSection() {
    final recommendationZones = _field.zones.where((z) => z.severity != null && z.severity!.toLowerCase() != 'none').toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
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
            final isCritical = zone.severity!.toLowerCase() == 'high' || zone.severity!.toLowerCase() == 'critical' || zone.severity!.toLowerCase() == 'moderate';
            return Padding(
              padding: const EdgeInsets.only(bottom: 16.0),
              child: Card(
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                  side: BorderSide(color: isCritical ? Colors.red.shade200 : Colors.grey.shade200, width: 1.5),
                ),
                color: isCritical ? Colors.red.shade50.withValues(alpha: 0.33) : Colors.white,
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
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              'Problem: ${zone.problem} in ${zone.name}',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 14,
                                color: isCritical ? Colors.red.shade900 : Colors.black87,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        'AI Assessment: ${zone.problem ?? "Field conditions are warning stress levels."}',
                        style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary, height: 1.3),
                      ),
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: AppTheme.primaryGreenSurface,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Solution: Action Required',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 13,
                                color: Colors.green.shade800,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              zone.recommendation ?? 'Monitor status regularly.',
                              style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary, height: 1.3),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          }),
      ],
    );
  }
}
