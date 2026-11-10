package com.example.app

import android.content.ContentValues
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.pdf.PdfRenderer
import android.os.Build
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.os.ParcelFileDescriptor
import android.provider.MediaStore
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "com.example.app/downloads")
            .setMethodCallHandler { call, result ->
                if (call.method == "extractPdfText" || call.method == "extractImageText") {
                    val isPdf = call.method == "extractPdfText"
                    val filePath = call.argument<String>("filePath")
                    if (filePath.isNullOrBlank()) {
                        result.error("INVALID_ARGUMENT", "A document file path is required.", null)
                        return@setMethodCallHandler
                    }

                    Thread({
                        try {
                            val extractedText = if (isPdf) {
                                extractPdfText(filePath)
                            } else {
                                extractImageText(filePath)
                            }
                            Handler(Looper.getMainLooper()).post {
                                result.success(extractedText)
                            }
                        } catch (error: Exception) {
                            Handler(Looper.getMainLooper()).post {
                                result.error("PDF_OCR_FAILED", error.message, null)
                            }
                        }
                    }, "soil-card-ocr").start()
                    return@setMethodCallHandler
                }

                if (call.method != "savePdfToDownloads") {
                    result.notImplemented()
                    return@setMethodCallHandler
                }

                val fileName = call.argument<String>("fileName")
                val bytes = call.argument<ByteArray>("bytes")
                if (fileName.isNullOrBlank() || bytes == null) {
                    result.error("INVALID_ARGUMENT", "A filename and PDF data are required.", null)
                    return@setMethodCallHandler
                }

                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
                    result.error("UNSUPPORTED_VERSION", "Public Downloads requires Android 10 or newer.", null)
                    return@setMethodCallHandler
                }

                try {
                    val values = ContentValues().apply {
                        put(MediaStore.Downloads.DISPLAY_NAME, fileName)
                        put(MediaStore.Downloads.MIME_TYPE, "application/pdf")
                        put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                        put(MediaStore.Downloads.IS_PENDING, 1)
                    }
                    val uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                        ?: throw IllegalStateException("Could not create the download file.")

                    try {
                        contentResolver.openOutputStream(uri)?.use { it.write(bytes) }
                            ?: throw IllegalStateException("Could not open the download file.")
                        values.clear()
                        values.put(MediaStore.Downloads.IS_PENDING, 0)
                        contentResolver.update(uri, values, null, null)
                        result.success(uri.toString())
                    } catch (error: Exception) {
                        contentResolver.delete(uri, null, null)
                        throw error
                    }
                } catch (error: Exception) {
                    result.error("SAVE_FAILED", error.message, null)
                }
            }
    }

    private fun extractPdfText(filePath: String): String {
        val file = File(filePath)
        if (!file.exists() || !file.isFile) {
            throw IllegalArgumentException("The selected PDF is no longer available. Please select it again.")
        }

        val output = StringBuilder()
        val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        try {
            ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY).use { descriptor ->
                PdfRenderer(descriptor).use { renderer ->
                    for (pageIndex in 0 until renderer.pageCount) {
                        renderer.openPage(pageIndex).use { page ->
                            val scale = minOf(3f, 3000f / maxOf(page.width, page.height))
                                .coerceAtLeast(1f)
                            val bitmap = Bitmap.createBitmap(
                                (page.width * scale).toInt(),
                                (page.height * scale).toInt(),
                                Bitmap.Config.ARGB_8888,
                            )
                            try {
                                bitmap.eraseColor(Color.WHITE)
                                page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                                val text = Tasks.await(
                                    recognizer.process(InputImage.fromBitmap(bitmap, 0)),
                                ).text
                                if (text.isNotBlank()) {
                                    output.append(text).append('\n')
                                }
                            } finally {
                                bitmap.recycle()
                            }
                        }
                    }
                }
            }
        } finally {
            recognizer.close()
        }
        return output.toString()
    }

    private fun extractImageText(filePath: String): String {
        val file = File(filePath)
        if (!file.exists() || !file.isFile) {
            throw IllegalArgumentException("The selected image is no longer available. Please select it again.")
        }

        val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        return try {
            Tasks.await(
                recognizer.process(InputImage.fromFilePath(this, android.net.Uri.fromFile(file))),
            ).text
        } finally {
            recognizer.close()
        }
    }
}
