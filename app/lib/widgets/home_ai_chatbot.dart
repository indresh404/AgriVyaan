import 'dart:async';
import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import 'dart:io';
import '../services/app_state.dart';
import '../services/sarvam_service.dart';
import '../utils/app_theme.dart';

class HomeAiChatbot extends StatefulWidget {
  const HomeAiChatbot({super.key});

  @override
  State<HomeAiChatbot> createState() => _HomeAiChatbotState();
}

class _HomeAiChatbotState extends State<HomeAiChatbot> {
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final AudioPlayer _audioPlayer = AudioPlayer();
  final AudioRecorder _audioRecorder = AudioRecorder();

  final List<Map<String, dynamic>> _messages = [];
  bool _isRecording = false;
  bool _isPlayingAudio = false;
  bool _isLoadingAi = false;
  String? _currentlyPlayingMsgId;

  final SarvamService _sarvamService = SarvamService();

  final List<Map<String, String>> _availableLanguages = [
    {'code': 'en', 'label': 'English'},
    {'code': 'hi', 'label': 'हिन्दी'},
    {'code': 'mr', 'label': 'मराठी'},
    {'code': 'gu', 'label': 'ગુજરાતી'},
    {'code': 'pa', 'label': 'ਪੰਜਾਬੀ'},
    {'code': 'kn', 'label': 'ಕನ್ನಡ'},
    {'code': 'te', 'label': 'తెలుగు'},
  ];

  @override
  void initState() {
    super.initState();
    _audioPlayer.onPlayerComplete.listen((_) {
      if (mounted) {
        setState(() {
          _isPlayingAudio = false;
          _currentlyPlayingMsgId = null;
        });
      }
    });
    // Add welcome message after first frame if history is empty
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final appState = AppStateProvider.of(context);
      if (appState.chatHistory.isEmpty) {
        appState.addChatMessage({
          'id': 'welcome_msg',
          'isUser': false,
          'text': 'Welcome to Agrivyaan! I am your AI Farming Assistant. Ask me anything about farming, or say "how to use" to learn about app features. You can speak in Hindi, Marathi, Gujarati, Punjabi, Kannada, or Telugu!',
          'timestamp': DateTime.now().toIso8601String(),
        });
      }
    });
  }

  @override
  void dispose() {
    _audioPlayer.dispose();
    _audioRecorder.dispose();
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final appState = AppStateProvider.of(context);
    final lang = appState.currentLanguage;

    final messagesList = appState.chatHistory;

    final quickPrompts = [
      appState.translate('prompt_health'),
      appState.translate('prompt_weather'),
      appState.translate('prompt_zone'),
      appState.translate('prompt_blight'),
    ];

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.06),
            blurRadius: 15,
            offset: const Offset(0, 6),
          ),
        ],
        border: Border.all(color: Colors.green.shade100, width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header Bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [AppTheme.primaryGreen, Colors.green.shade700],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(18)),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.2),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.psychology, color: Colors.white, size: 22),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(child: Text(
                            appState.translate('ai_assistant'),
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              fontSize: 16,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          )),
                        ],
                      ),
                      Text(
                        appState.translate('ai_assistant_sub'),
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.9),
                          fontSize: 11,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
                // Language Dropdown selector right inside chatbot
                PopupMenuButton<String>(
                  icon: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.translate, color: Colors.white, size: 14),
                        const SizedBox(width: 4),
                        Text(
                          lang.toUpperCase(),
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const Icon(Icons.arrow_drop_down, color: Colors.white, size: 16),
                      ],
                    ),
                  ),
                  onSelected: (newLang) {
                    appState.setLanguage(newLang);
                  },
                  itemBuilder: (context) {
                    return _availableLanguages.map((l) {
                      final isSel = l['code'] == lang;
                      return PopupMenuItem<String>(
                        value: l['code'],
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              l['label']!,
                              style: TextStyle(
                                fontWeight: isSel ? FontWeight.bold : FontWeight.normal,
                                color: isSel ? AppTheme.primaryGreen : Colors.black87,
                              ),
                            ),
                            if (isSel)
                              const Icon(Icons.check, color: AppTheme.primaryGreen, size: 16),
                          ],
                        ),
                      );
                    }).toList();
                  },
                ),
                const SizedBox(width: 4),
                IconButton(
                  icon: const Icon(Icons.delete_outline, color: Colors.white, size: 18),
                  tooltip: 'Clear History',
                  onPressed: () {
                    appState.clearChatHistory();
                  },
                ),
              ],
            ),
          ),

          // Messages Box
          Container(
            constraints: const BoxConstraints(maxHeight: 250),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: ListView.builder(
              controller: _scrollController,
              shrinkWrap: true,
              itemCount: messagesList.length,
              itemBuilder: (context, index) {
                final msg = messagesList[index];
                final isUser = msg['isUser'] as bool;
                final msgId = msg['id'] as String;
                final isThisPlaying = _currentlyPlayingMsgId == msgId && _isPlayingAudio;

                return Align(
                  alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 10),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
                    decoration: BoxDecoration(
                      color: isUser ? AppTheme.primaryGreen : Colors.grey.shade100,
                      borderRadius: BorderRadius.only(
                        topLeft: const Radius.circular(16),
                        topRight: const Radius.circular(16),
                        bottomLeft: Radius.circular(isUser ? 16 : 2),
                        bottomRight: Radius.circular(isUser ? 2 : 16),
                      ),
                      border: isUser ? null : Border.all(color: Colors.grey.shade300),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          msg['text'] as String,
                          style: TextStyle(
                            color: isUser ? Colors.white : Colors.black87,
                            fontSize: 13.5,
                            height: 1.35,
                          ),
                        ),
                        if (!isUser) ...[
                          const SizedBox(height: 6),
                          InkWell(
                            onTap: () => _toggleTtsAudio(msg['text'] as String, msgId, lang),
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: isThisPlaying ? Colors.amber.shade100 : Colors.green.shade50,
                                borderRadius: BorderRadius.circular(10),
                                border: Border.all(
                                  color: isThisPlaying ? Colors.amber.shade600 : Colors.green.shade300,
                                ),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(
                                    isThisPlaying ? Icons.stop_circle : Icons.volume_up,
                                    size: 14,
                                    color: isThisPlaying ? Colors.amber.shade900 : Colors.green.shade800,
                                  ),
                                  const SizedBox(width: 4),
                                  Text(
                                    isThisPlaying
                                        ? appState.translate('stop_audio')
                                        : appState.translate('listen_audio'),
                                    style: TextStyle(
                                      fontSize: 10.5,
                                      fontWeight: FontWeight.bold,
                                      color: isThisPlaying ? Colors.amber.shade900 : Colors.green.shade800,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                );
              },
            ),
          ),

          // Loading AI Indicator
          if (_isLoadingAi)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              child: Row(
                children: [
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.primaryGreen),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'Preparing your answer...',
                    style: TextStyle(fontSize: 11, fontStyle: FontStyle.italic, color: Colors.grey.shade600),
                  ),
                ],
              ),
            ),

          // Voice Recording Status Banner
          if (_isRecording)
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.red.shade50,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.red.shade200),
              ),
              child: Row(
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: const BoxDecoration(
                      color: Colors.red,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      appState.translate('listening'),
                      style: const TextStyle(color: Colors.red, fontSize: 12, fontWeight: FontWeight.bold),
                    ),
                  ),
                  InkWell(
                    onTap: () => _stopVoiceRecording(appState),
                    child: const Icon(Icons.check_circle, color: Colors.red, size: 22),
                  ),
                ],
              ),
            ),

          // Quick Suggestion Chips
          SizedBox(
            height: 42,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 10),
              itemCount: quickPrompts.length,
              itemBuilder: (context, idx) {
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: ActionChip(
                    label: Text(
                      quickPrompts[idx],
                      style: const TextStyle(fontSize: 11, color: Colors.black87),
                    ),
                    backgroundColor: Colors.grey.shade50,
                    side: BorderSide(color: Colors.green.shade200),
                    onPressed: () {
                      _sendMessage(quickPrompts[idx], appState);
                    },
                  ),
                );
              },
            ),
          ),

          const SizedBox(height: 4),

          // Input controls
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.grey.shade50,
              borderRadius: const BorderRadius.vertical(bottom: Radius.circular(18)),
              border: Border(top: BorderSide(color: Colors.grey.shade200)),
            ),
            child: Row(
              children: [
                // Speech-to-Text Microphone Button
                GestureDetector(
                  onTap: () {
                    if (_isRecording) {
                      _stopVoiceRecording(appState);
                    } else {
                      _startVoiceRecording(appState);
                    }
                  },
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: _isRecording ? Colors.red : AppTheme.primaryGreenSurface,
                      shape: BoxShape.circle,
                      boxShadow: _isRecording
                          ? [BoxShadow(color: Colors.red.withOpacity(0.4), blurRadius: 8, spreadRadius: 2)]
                          : null,
                    ),
                    child: Icon(
                      _isRecording ? Icons.mic : Icons.mic_none,
                      color: _isRecording ? Colors.white : AppTheme.primaryGreen,
                      size: 20,
                    ),
                  ),
                ),
                const SizedBox(width: 8),

                // Text Input
                Expanded(
                  child: TextField(
                    controller: _inputController,
                    decoration: InputDecoration(
                      hintText: appState.translate('type_or_speak'),
                      hintStyle: TextStyle(fontSize: 12, color: Colors.grey.shade500),
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 8),
                    ),
                    onSubmitted: (val) {
                      if (val.trim().isNotEmpty) {
                        _sendMessage(val.trim(), appState);
                      }
                    },
                  ),
                ),

                // Send Button
                IconButton(
                  icon: const Icon(Icons.send_rounded, color: AppTheme.primaryGreen, size: 22),
                  onPressed: () {
                    final text = _inputController.text.trim();
                    if (text.isNotEmpty) {
                      _sendMessage(text, appState);
                    }
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _sendMessage(String query, AppState appState) async {
    if (_isLoadingAi || query.trim().isEmpty) return;
    final msgId = DateTime.now().millisecondsSinceEpoch.toString();
    
    appState.addChatMessage({
      'id': 'user_$msgId',
      'isUser': true,
      'text': query,
      'timestamp': DateTime.now().toIso8601String(),
    });

    setState(() {
      _inputController.clear();
      _isLoadingAi = true;
    });
    _scrollToBottom();

    String response;
    var shouldPlayAudio = false;
    try {
      response = await _sarvamService.generateFarmerResponse(
        query: query,
        languageCode: appState.currentLanguage,
        profile: appState.currentProfile,
        fields: appState.fields,
        chatHistory: appState.chatHistory,
      );
      shouldPlayAudio = true;
    } catch (error, stackTrace) {
      debugPrint('Chatbot response error: $error\n$stackTrace');
      response = 'Sorry, I couldn’t prepare a response right now. Please try again.';
    } finally {
      if (mounted) {
        setState(() => _isLoadingAi = false);
      }
    }

    if (!mounted) return;

    final botMsgId = 'bot_$msgId';
    appState.addChatMessage({
      'id': botMsgId,
      'isUser': false,
      'text': response,
      'timestamp': DateTime.now().toIso8601String(),
    });
    _scrollToBottom();

    // Only play generated responses. Error messages should stay quiet.
    if (shouldPlayAudio) {
      _toggleTtsAudio(response, botMsgId, appState.currentLanguage);
    }
  }

  void _startVoiceRecording(AppState appState) async {
    try {
      if (await _audioRecorder.hasPermission()) {
        final dir = await getTemporaryDirectory();
        final path = '${dir.path}/sarvam_speech.wav';

        await _audioRecorder.start(
          const RecordConfig(encoder: AudioEncoder.wav, sampleRate: 16000),
          path: path,
        );

        setState(() {
          _isRecording = true;
        });

        // Auto stop after 5 seconds
        Timer(const Duration(seconds: 5), () {
          if (_isRecording && mounted) {
            _stopVoiceRecording(appState);
          }
        });
      } else {
        _simulateVoiceInput(appState);
      }
    } catch (e) {
      debugPrint('Audio recording error: $e. Falling back to voice simulation...');
      _simulateVoiceInput(appState);
    }
  }

  void _stopVoiceRecording(AppState appState) async {
    if (!_isRecording) return;
    setState(() {
      _isRecording = false;
    });

    try {
      final path = await _audioRecorder.stop();
      if (path != null) {
        final file = File(path);
        if (await file.exists()) {
          final bytes = await file.readAsBytes();
          // Call Sarvam STT API
          final transcript = await _sarvamService.speechToText(
            audioBytes: bytes,
            languageCode: appState.currentLanguage,
          );

          if (transcript != null && transcript.trim().isNotEmpty) {
            _sendMessage(transcript, appState);
            return;
          }
        }
      }
    } catch (e) {
      debugPrint('Error stopping recording/STT: $e');
    }

    _simulateVoiceInput(appState);
  }

  void _simulateVoiceInput(AppState appState) {
    setState(() {
      _isRecording = false;
    });
    final lang = appState.currentLanguage;
    String sampleVoiceQuery = appState.translate('prompt_health');
    if (lang == 'hi') {
      sampleVoiceQuery = 'मेरे खेत में क्या समस्या है?';
    } else if (lang == 'mr') {
      sampleVoiceQuery = 'माझ्या शेतात काय अडचण आहे?';
    } else if (lang == 'gu') {
      sampleVoiceQuery = 'મારા ખેતરમાં શું તકલીફ છે?';
    }
    _sendMessage(sampleVoiceQuery, appState);
  }

  void _toggleTtsAudio(String text, String msgId, String langCode) async {
    if (_currentlyPlayingMsgId == msgId && _isPlayingAudio) {
      await _audioPlayer.stop();
      setState(() {
        _isPlayingAudio = false;
        _currentlyPlayingMsgId = null;
      });
      return;
    }

    await _audioPlayer.stop();
    setState(() {
      _isPlayingAudio = true;
      _currentlyPlayingMsgId = msgId;
    });

    // Request Sarvam TTS Audio
    final audioBytes = await _sarvamService.textToSpeech(
      text: text,
      languageCode: langCode,
    );

    if (audioBytes != null && mounted) {
      try {
        await _audioPlayer.play(BytesSource(audioBytes));
      } catch (e) {
        debugPrint('Error playing Sarvam audio: $e');
        setState(() {
          _isPlayingAudio = false;
          _currentlyPlayingMsgId = null;
        });
      }
    } else {
      if (mounted) {
        setState(() {
          _isPlayingAudio = false;
          _currentlyPlayingMsgId = null;
        });
      }
    }
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 150), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }
}
