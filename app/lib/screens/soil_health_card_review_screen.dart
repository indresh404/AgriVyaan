import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import '../models/soil_health_card.dart';
import '../services/app_state.dart';
import '../utils/app_theme.dart';

/// Review and edit screen for Soil Health Card data.
/// Used after extraction (new card) or for editing existing card details.
/// All fields are editable so the farmer can correct OCR/extraction errors.
class SoilHealthCardReviewScreen extends StatefulWidget {
  final SoilHealthCard card;
  final String fieldName;
  final String? sourceFilePath;
  final bool isNewCard;

  const SoilHealthCardReviewScreen({
    super.key,
    required this.card,
    required this.fieldName,
    this.sourceFilePath,
    this.isNewCard = false,
  });

  @override
  State<SoilHealthCardReviewScreen> createState() =>
      _SoilHealthCardReviewScreenState();
}

class _SoilHealthCardReviewScreenState
    extends State<SoilHealthCardReviewScreen> {
  late final Map<String, TextEditingController> _controllers;
  late final Map<String, TextEditingController> _nutrientControllers;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _initControllers();
  }

  void _initControllers() {
    final card = widget.card;
    final dateFormat = DateFormat('dd/MM/yyyy');

    _controllers = {
      'cardNumber': TextEditingController(text: card.cardNumber ?? ''),
      'sampleId': TextEditingController(text: card.sampleId ?? ''),
      'farmerName': TextEditingController(text: card.farmerName ?? ''),
      'fatherHusbandName':
          TextEditingController(text: card.fatherHusbandName ?? ''),
      'village': TextEditingController(text: card.village ?? ''),
      'tehsil': TextEditingController(text: card.tehsil ?? ''),
      'district': TextEditingController(text: card.district ?? ''),
      'state': TextEditingController(text: card.state ?? ''),
      'totalLandHolding':
          TextEditingController(text: card.totalLandHolding ?? ''),
      'soilType': TextEditingController(text: card.soilType ?? ''),
      'soilColour': TextEditingController(text: card.soilColour ?? ''),
      'soilTexture': TextEditingController(text: card.soilTexture ?? ''),
      'location': TextEditingController(text: card.location ?? ''),
      'sampleDate': TextEditingController(
        text: card.sampleDate != null
            ? dateFormat.format(card.sampleDate!)
            : '',
      ),
      'fertilizerRecommendations': TextEditingController(
        text: card.fertilizerRecommendations.join('\n'),
      ),
      'nutrientRecommendations': TextEditingController(
        text: card.nutrientRecommendations.join('\n'),
      ),
      'cropRecommendations': TextEditingController(
        text: card.cropRecommendations.join('\n'),
      ),
    };

    _nutrientControllers = {};
    for (final nutrient in card.nutrients) {
      _nutrientControllers[nutrient.name] = TextEditingController(
        text: nutrient.value == 0 ? '' : nutrient.value.toString(),
      );
    }
  }

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    for (final c in _nutrientControllers.values) {
      c.dispose();
    }
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
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Review Soil Information',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
            ),
            Text(
              widget.fieldName,
              style: const TextStyle(
                fontSize: 12,
                color: AppTheme.textSecondary,
                fontWeight: FontWeight.w400,
              ),
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          // Verification banner
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(
                horizontal: 16, vertical: 10),
            color: AppTheme.warning.withValues(alpha: 0.08),
            child: Row(
              children: [
                Icon(Icons.rate_review_outlined,
                    size: 18,
                    color: AppTheme.warning),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text(
                    'Please verify the extracted information before saving.',
                    style: TextStyle(
                      fontSize: 12,
                      color: AppTheme.textPrimary,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ],
            ),
          ),
          // Form
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _buildSectionHeader('Farmer & Card Details'),
                const SizedBox(height: 12),
                _buildTextField('Card Number', 'cardNumber'),
                _buildTextField('Sample ID', 'sampleId'),
                _buildTextField('Farmer Name', 'farmerName'),
                _buildTextField(
                    'Father / Husband Name', 'fatherHusbandName'),
                _buildTextField('Village', 'village'),
                _buildTextField('Tehsil', 'tehsil'),
                _buildTextField('District', 'district'),
                _buildTextField('State', 'state'),
                _buildTextField('Total Land Holding', 'totalLandHolding'),
                _buildTextField('Sample Date (DD/MM/YYYY)', 'sampleDate'),
                const SizedBox(height: 20),

                _buildSectionHeader('Soil Characteristics'),
                const SizedBox(height: 12),
                _buildTextField('Soil Type', 'soilType'),
                _buildTextField('Soil Colour', 'soilColour'),
                _buildTextField('Soil Texture', 'soilTexture'),
                _buildTextField('Location', 'location'),
                const SizedBox(height: 20),

                // Nutrients by category
                ..._buildNutrientSections(),

                _buildSectionHeader('Recommendations'),
                const SizedBox(height: 12),
                _buildMultilineField(
                    'Fertilizer Recommendations',
                    'fertilizerRecommendations',
                    'One recommendation per line'),
                _buildMultilineField(
                    'Nutrient Recommendations',
                    'nutrientRecommendations',
                    'One recommendation per line'),
                _buildMultilineField(
                    'Crop Suggestions',
                    'cropRecommendations',
                    'One crop per line'),
                const SizedBox(height: 24),

                // Save button
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _isSaving ? null : _confirmAndSave,
                    icon: _isSaving
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.verified_outlined),
                    label: Text(
                        _isSaving ? 'Saving...' : 'Confirm & Save'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primaryGreen,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      textStyle: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 32),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppTheme.primaryGreenSurface,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Icon(Icons.eco_rounded,
              size: 16, color: AppTheme.primaryGreenDark),
          const SizedBox(width: 8),
          Text(
            title,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: AppTheme.primaryGreenDark,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTextField(String label, String key) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: _controllers[key],
        decoration: InputDecoration(
          labelText: label,
          filled: true,
          fillColor: Colors.white,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppTheme.border),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppTheme.border),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide:
                const BorderSide(color: AppTheme.primaryGreen, width: 1.5),
          ),
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        ),
      ),
    );
  }

  Widget _buildMultilineField(
      String label, String key, String hint) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: _controllers[key],
        maxLines: 3,
        decoration: InputDecoration(
          labelText: label,
          hintText: hint,
          filled: true,
          fillColor: Colors.white,
          alignLabelWithHint: true,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppTheme.border),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppTheme.border),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide:
                const BorderSide(color: AppTheme.primaryGreen, width: 1.5),
          ),
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        ),
      ),
    );
  }

  List<Widget> _buildNutrientSections() {
    final widgets = <Widget>[];
    for (final category in NutrientCategory.values) {
      final readings = widget.card.getNutrientsByCategory(category);
      if (readings.isEmpty) continue;

      widgets.add(_buildSectionHeader(category.displayName));
      widgets.add(const SizedBox(height: 12));

      for (final reading in readings) {
        final controller = _nutrientControllers[reading.name];
        if (controller == null) continue;
        widgets.add(
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: TextFormField(
              controller: controller,
              keyboardType:
                  const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: [
                FilteringTextInputFormatter.allow(
                    RegExp(r'[0-9.]')),
              ],
              decoration: InputDecoration(
                labelText: reading.name,
                suffixText: reading.unit.isNotEmpty ? reading.unit : null,
                filled: true,
                fillColor: Colors.white,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppTheme.border),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppTheme.border),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(
                      color: AppTheme.primaryGreen, width: 1.5),
                ),
                contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16, vertical: 14),
              ),
            ),
          ),
        );
      }
      widgets.add(const SizedBox(height: 20));
    }
    return widgets;
  }

  Future<void> _confirmAndSave() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Confirm soil test values'),
        content: const Text(
          'Have you checked the extracted values and corrected anything that was read incorrectly? Confirm to save this report.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Review again'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Yes, save'),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) await _saveAndVerify();
  }

  Future<void> _saveAndVerify() async {
    setState(() => _isSaving = true);

    try {
      // Parse sample date
      DateTime? sampleDate;
      final dateStr = _controllers['sampleDate']!.text.trim();
      if (dateStr.isNotEmpty) {
        try {
          sampleDate = DateFormat('dd/MM/yyyy').parse(dateStr);
        } catch (_) {
          // If parse fails, try ISO format
          sampleDate = DateTime.tryParse(dateStr);
        }
      }

      // Build updated nutrients with edited values
      final updatedNutrients = widget.card.nutrients.where((original) {
        return _nutrientControllers[original.name]?.text.trim().isNotEmpty ??
            false;
      }).map((original) {
        final controller = _nutrientControllers[original.name];
        if (controller == null) return original;
        final newValue = double.tryParse(controller.text.trim());
        if (newValue == null) {
          throw FormatException('Enter a valid number for ${original.name}.');
        }
        return original.copyWith(value: newValue);
      }).toList();

      // Parse multiline recommendations
      List<String> parseLines(String key) {
        return _controllers[key]!
            .text
            .split('\n')
            .map((s) => s.trim())
            .where((s) => s.isNotEmpty)
            .toList();
      }

      // Build the verified card
      final verifiedCard = widget.card.copyWith(
        cardNumber: _controllers['cardNumber']!.text.trim().isNotEmpty
            ? _controllers['cardNumber']!.text.trim()
            : null,
        sampleId: _controllers['sampleId']!.text.trim().isNotEmpty
            ? _controllers['sampleId']!.text.trim()
            : null,
        farmerName: _controllers['farmerName']!.text.trim().isNotEmpty
            ? _controllers['farmerName']!.text.trim()
            : null,
        fatherHusbandName:
            _controllers['fatherHusbandName']!.text.trim().isNotEmpty
                ? _controllers['fatherHusbandName']!.text.trim()
                : null,
        village: _controllers['village']!.text.trim().isNotEmpty
            ? _controllers['village']!.text.trim()
            : null,
        tehsil: _controllers['tehsil']!.text.trim().isNotEmpty
            ? _controllers['tehsil']!.text.trim()
            : null,
        district: _controllers['district']!.text.trim().isNotEmpty
            ? _controllers['district']!.text.trim()
            : null,
        state: _controllers['state']!.text.trim().isNotEmpty
            ? _controllers['state']!.text.trim()
            : null,
        totalLandHolding:
            _controllers['totalLandHolding']!.text.trim().isNotEmpty
                ? _controllers['totalLandHolding']!.text.trim()
                : null,
        sampleDate: sampleDate ?? widget.card.sampleDate,
        soilType: _controllers['soilType']!.text.trim().isNotEmpty
            ? _controllers['soilType']!.text.trim()
            : null,
        soilColour: _controllers['soilColour']!.text.trim().isNotEmpty
            ? _controllers['soilColour']!.text.trim()
            : null,
        soilTexture: _controllers['soilTexture']!.text.trim().isNotEmpty
            ? _controllers['soilTexture']!.text.trim()
            : null,
        location: _controllers['location']!.text.trim().isNotEmpty
            ? _controllers['location']!.text.trim()
            : null,
        nutrients: updatedNutrients,
        fertilizerRecommendations:
            parseLines('fertilizerRecommendations'),
        nutrientRecommendations:
            parseLines('nutrientRecommendations'),
        cropRecommendations: parseLines('cropRecommendations'),
        isVerified: true,
        isCurrent: true,
      );

      final appState = AppStateProvider.of(context);

      if (widget.isNewCard) {
        await appState.addSoilHealthCard(
          verifiedCard.fieldId,
          verifiedCard,
          localFilePath: widget.sourceFilePath,
        );
      } else {
        await appState.updateSoilHealthCard(
            verifiedCard.fieldId, verifiedCard);
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Row(
              children: [
                Icon(Icons.verified_rounded,
                    color: Colors.white, size: 18),
                SizedBox(width: 8),
                Text('Soil Health Card saved & verified ✓'),
              ],
            ),
            backgroundColor: AppTheme.primaryGreen,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        );
        // Pop back to the SHC screen or field overview
        Navigator.of(context).pop();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error saving: $e'),
            backgroundColor: AppTheme.error,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }
}
