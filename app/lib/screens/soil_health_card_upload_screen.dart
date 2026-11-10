import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import '../models/soil_health_card.dart';
import '../services/app_state.dart';
import '../services/soil_health_card_extraction_service.dart';
import '../utils/app_theme.dart';
import 'soil_health_card_review_screen.dart';

/// Screen for uploading a Soil Health Card PDF and reviewing extracted values.
class SoilHealthCardUploadScreen extends StatefulWidget {
  final String fieldId;
  final String fieldName;

  const SoilHealthCardUploadScreen({
    super.key,
    required this.fieldId,
    required this.fieldName,
  });

  @override
  State<SoilHealthCardUploadScreen> createState() =>
      _SoilHealthCardUploadScreenState();
}

enum _UploadState { initial, picking, processing, done, error }

class _SoilHealthCardUploadScreenState
    extends State<SoilHealthCardUploadScreen>
    with SingleTickerProviderStateMixin {
  _UploadState _state = _UploadState.initial;
  String? _selectedFileName;
  String? _selectedFilePath;
  String? _errorMessage;
  Map<String, double?> _extractedValues = {};
  final SoilHealthCardExtractionService _extractionService =
      SoilHealthCardExtractionService();
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.scaffoldBackground,
      appBar: AppBar(
        backgroundColor: Colors.white,
        foregroundColor: AppTheme.textPrimary,
        elevation: 0.5,
        title: const Text(
          'Upload Soil Health Card',
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
        ),
      ),
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 300),
        child: _buildBody(),
      ),
    );
  }

  Widget _buildBody() {
    switch (_state) {
      case _UploadState.initial:
        return _buildInitialState();
      case _UploadState.picking:
        return _buildProcessingState('Selecting file...');
      case _UploadState.processing:
        return _buildProcessingState('Reading Soil Health Card...');
      case _UploadState.done:
        return _buildDoneState();
      case _UploadState.error:
        return _buildErrorState();
    }
  }

  Widget _buildInitialState() {
    return ListView(
      key: const ValueKey('initial'),
      padding: const EdgeInsets.all(24),
      children: [
        // Header info
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: AppTheme.primaryGreenSurface,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            children: [
              const Icon(Icons.eco_outlined,
                  size: 40, color: AppTheme.primaryGreen),
              const SizedBox(height: 12),
              const Text(
                'Add Soil Health Card',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Add the soil report for ${widget.fieldName} to create its soil baseline.',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 13,
                  color: AppTheme.textSecondary,
                  height: 1.4,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),

        // Upload PDF
        _buildUploadOption(
          icon: Icons.picture_as_pdf_rounded,
          title: 'Upload PDF',
          subtitle: 'Select a PDF copy of the Soil Health Card',
          color: Colors.red.shade400,
          onTap: () => _pickFile(['pdf']),
        ),
        const SizedBox(height: 12),

        _buildUploadOption(
          icon: Icons.image_outlined,
          title: 'Upload Image',
          subtitle: 'Select a photo or scanned image of the card',
          color: Colors.blue.shade400,
          onTap: () => _pickFile(['jpg', 'jpeg', 'png', 'webp']),
        ),
        const SizedBox(height: 12),

        // Scan / Import
        _buildUploadOption(
          icon: Icons.qr_code_scanner_rounded,
          title: 'Scan / Import Card',
          subtitle: 'QR scanning integration — coming soon',
          color: Colors.purple.shade400,
          onTap: _showScanComingSoon,
          isDisabled: true,
        ),

        const SizedBox(height: 24),

        // Info banner
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppTheme.info.withValues(alpha: 0.06),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
                color: AppTheme.info.withValues(alpha: 0.15)),
          ),
          child: const Row(
            children: [
              Icon(Icons.info_outline_rounded,
                  size: 16, color: AppTheme.info),
              SizedBox(width: 8),
              Expanded(
                child: Text(
                  'The uploaded document will be processed and extracted values can be reviewed and corrected before saving.',
                  style: TextStyle(
                    fontSize: 12,
                    color: AppTheme.textSecondary,
                    height: 1.3,
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildUploadOption({
    required IconData icon,
    required String title,
    required String subtitle,
    required Color color,
    required VoidCallback onTap,
    bool isDisabled = false,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: isDisabled ? onTap : onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: isDisabled
                  ? AppTheme.border
                  : color.withValues(alpha: 0.3),
              width: 0.5,
            ),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: isDisabled
                      ? Colors.grey.shade100
                      : color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon,
                    color: isDisabled ? Colors.grey : color, size: 24),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: isDisabled
                            ? AppTheme.textSecondary
                            : AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                isDisabled
                    ? Icons.lock_outline_rounded
                    : Icons.chevron_right_rounded,
                color: AppTheme.textLight,
                size: 20,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildProcessingState(String message) {
    return Center(
      key: const ValueKey('processing'),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          AnimatedBuilder(
            animation: _pulseController,
            builder: (context, child) {
              return Transform.scale(
                scale: 0.9 + (_pulseController.value * 0.2),
                child: child,
              );
            },
            child: Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: AppTheme.primaryGreenSurface,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.eco_outlined,
                size: 40,
                color: AppTheme.primaryGreen,
              ),
            ),
          ),
          const SizedBox(height: 24),
          Text(
            message,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          if (_selectedFileName != null)
            Text(
              _selectedFileName!,
              style: const TextStyle(
                fontSize: 13,
                color: AppTheme.textSecondary,
              ),
            ),
          const SizedBox(height: 24),
          const SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(
              strokeWidth: 2.5,
              color: AppTheme.primaryGreen,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDoneState() {
    return Center(
      key: const ValueKey('done'),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: AppTheme.primaryGreenSurface,
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.check_circle_rounded,
              size: 48,
              color: AppTheme.primaryGreen,
            ),
          ),
          const SizedBox(height: 20),
          Text(
            _extractedValues.values.any((value) => value != null)
                ? 'Information extracted successfully'
                : 'PDF opened; enter values below',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            _extractedValues.values.any((value) => value != null)
                ? 'Please review and verify the extracted data.'
                : 'No soil values were recognized. You can enter them manually in the review form.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 13,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _navigateToReview,
            icon: const Icon(Icons.rate_review_outlined),
            label: const Text('Review Information'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryGreen,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(
                  horizontal: 24, vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState() {
    return Center(
      key: const ValueKey('error'),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline_rounded,
              size: 48, color: AppTheme.error),
          const SizedBox(height: 16),
          const Text(
            'Failed to process document',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            _errorMessage ?? 'Please try again or select a different file.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppTheme.textSecondary),
          ),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: () => setState(() => _state = _UploadState.initial),
            child: const Text('Try Again'),
          ),
        ],
      ),
    );
  }

  Future<void> _pickFile(List<String> allowedExtensions) async {
    setState(() {
      _state = _UploadState.picking;
      _errorMessage = null;
    });

    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: allowedExtensions,
        withData: false,
      );

      if (result == null || result.files.isEmpty) {
        // User cancelled
        setState(() => _state = _UploadState.initial);
        return;
      }

      _selectedFileName = result.files.first.name;
      _selectedFilePath = result.files.first.path;
      if (_selectedFilePath == null) {
        throw const FormatException('Could not open the selected document.');
      }
      setState(() => _state = _UploadState.processing);

      final isPdf = allowedExtensions.contains('pdf');
      _extractedValues = await _extractionService.extractValues(
        _selectedFilePath!,
        isPdf: isPdf,
      );
      setState(() => _state = _UploadState.done);
    } catch (e) {
      debugPrint('Soil Health Card OCR failed: $e');
      _errorMessage = e is FormatException
          ? e.message.toString()
          : e is PlatformException && e.message != null
              ? e.message!
              : e is UnsupportedError
                  ? e.message ?? 'This file type is not supported on this device.'
              : e.toString();
      setState(() => _state = _UploadState.error);
    }
  }

  void _showScanComingSoon() {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text(
          'QR / Scan import is being prepared for integration.',
        ),
        backgroundColor: AppTheme.info,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
    );
  }

  void _navigateToReview() {
    const nutrientDefinitions = <(String, String, NutrientCategory)>[
      ('pH', '', NutrientCategory.soilProperty),
      ('EC', 'dS/m', NutrientCategory.soilProperty),
      ('Organic Carbon', '%', NutrientCategory.soilProperty),
      ('Nitrogen (N)', 'kg/ha', NutrientCategory.macronutrient),
      ('Phosphorus (P)', 'kg/ha', NutrientCategory.macronutrient),
      ('Potassium (K)', 'kg/ha', NutrientCategory.macronutrient),
      ('Sulphur (S)', 'mg/kg', NutrientCategory.secondaryNutrient),
      ('Magnesium (Mg)', 'mg/kg', NutrientCategory.secondaryNutrient),
      ('Zinc (Zn)', 'mg/kg', NutrientCategory.micronutrient),
      ('Iron (Fe)', 'mg/kg', NutrientCategory.micronutrient),
      ('Copper (Cu)', 'mg/kg', NutrientCategory.micronutrient),
      ('Boron (B)', 'mg/kg', NutrientCategory.micronutrient),
    ];
    final nutrients = nutrientDefinitions.map((definition) {
      final (name, unit, category) = definition;
      return SoilNutrientReading(
        name: name,
        value: _extractedValues[name] ?? 0,
        unit: unit,
        status: NutrientStatus.normal,
        category: category,
      );
    }).toList();
    final appState = AppStateProvider.of(context);
    final extractedCard = SoilHealthCard(
      id: 'shc_${DateTime.now().millisecondsSinceEpoch}',
      fieldId: widget.fieldId,
      farmerName: appState.currentProfile?.name,
      location: appState.currentProfile?.location,
      uploadDate: DateTime.now(),
      nutrients: nutrients,
      sourceFileName: _selectedFileName,
      isVerified: false,
      isCurrent: false,
    );

    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => SoilHealthCardReviewScreen(
          card: extractedCard,
          fieldName: widget.fieldName,
          sourceFilePath: _selectedFilePath,
          isNewCard: true,
        ),
      ),
    );
  }
}
