import 'package:flutter/material.dart';
import '../services/app_state.dart';
import '../widgets/home_ai_chatbot.dart';
import '../utils/app_theme.dart';

class ChatScreen extends StatelessWidget {
  final String? prefilledPrompt;

  const ChatScreen({super.key, this.prefilledPrompt});

  @override
  Widget build(BuildContext context) {
    final appState = AppStateProvider.of(context);

    return Scaffold(
      backgroundColor: Colors.grey.shade50,
      appBar: AppBar(
        title: Row(
          children: [
            const Icon(Icons.psychology, color: AppTheme.primaryGreen),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                appState.translate('ai_assistant'),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.black87),
              ),
            ),
          ],
        ),
        backgroundColor: Colors.white,
        foregroundColor: Colors.black,
        elevation: 0,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Connected Farm Info Header
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.green.shade50,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.green.shade200),
                ),
                child: Row(
                  children: [
                    Icon(Icons.sensors, color: Colors.green.shade800, size: 20),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Connected Intelligence: ${appState.fields.length} Registered Fields (${appState.currentProfile?.location ?? "Wardha, Maharashtra"})',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: Colors.green.shade900,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              // Embedded Sarvam AI Chatbot Component
              const HomeAiChatbot(),
            ],
          ),
        ),
      ),
    );
  }
}
