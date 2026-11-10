import 'dart:io';
import 'package:flutter/services.dart';
import 'package:flutter_pdf_text/flutter_pdf_text.dart';

/// Extracts soil measurements from Soil Health Card PDFs and images.
class SoilHealthCardExtractionService {
  static const MethodChannel _androidPdfChannel =
      MethodChannel('com.example.app/downloads');

  Future<Map<String, double?>> extractValues(
    String filePath, {
    required bool isPdf,
  }) async {
    final String text;
    if (Platform.isAndroid) {
      text = await _androidPdfChannel.invokeMethod<String>(
            isPdf ? 'extractPdfText' : 'extractImageText',
            {'filePath': filePath},
          ) ??
          '';
    } else if (isPdf) {
      text = await _extractSelectableText(filePath);
    } else {
      throw UnsupportedError(
        'Image OCR is currently available on Android. Please upload a PDF on this device.',
      );
    }
    if (text.trim().isEmpty) {
      throw const FormatException(
        'No text was detected. Make sure the image is clear and the full card is visible.',
      );
    }

    return {
      'pH': _valueAfter(text, [r'p\s*H']),
      'EC': _valueAfter(text, [r'EC', r'electrical\s+conductivity']),
      'Organic Carbon': _valueAfter(text, [r'organic\s+carbon']),
      'Nitrogen (N)': _valueAfter(text, [r'available\s+nitrogen', r'nitrogen']),
      'Phosphorus (P)': _valueAfter(text, [r'available\s+phosphorus', r'phosphorus']),
      'Potassium (K)': _valueAfter(text, [r'available\s+potassium', r'potassium']),
      'Sulphur (S)': _valueAfter(text, [r'sulphur', r'sulfur']),
      'Zinc (Zn)': _valueAfter(text, [r'zinc']),
      'Iron (Fe)': _valueAfter(text, [r'iron']),
      'Copper (Cu)': _valueAfter(text, [r'copper']),
      'Magnesium (Mg)': _valueAfter(text, [r'magnesium']),
      'Boron (B)': _valueAfter(text, [r'boron']),
    };
  }

  Future<String> _extractSelectableText(String filePath) async {
    final document = await PDFDoc.fromPath(filePath);
    return document.text;
  }

  double? _valueAfter(String text, List<String> labels) {
    for (final label in labels) {
      final pattern = RegExp(
        '\\b$label\\b\\s*(?:\\([^)]*\\))?\\s*[:=\\-]?\\s*(?:<|>)?\\s*(-?\\d+(?:[.,]\\d+)?)',
        caseSensitive: false,
      );
      final match = pattern.firstMatch(text);
      if (match == null) continue;
      final value = double.tryParse(match.group(1)!.replaceAll(',', '.'));
      if (value != null) return value;
    }
    return null;
  }
}
