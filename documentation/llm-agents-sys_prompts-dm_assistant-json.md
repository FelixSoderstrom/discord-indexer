# src/llm/agents/sys_prompts/dm_assistant.json Documentation

## Purpose
System prompt configuration for the Discord DM Assistant agent. Defines the agent's personality, behavior guidelines, and response formatting instructions in a maintainable JSON format separate from code.

## What It Does
1. **Agent Personality**: Defines the assistant's conversational style and approach
2. **Behavior Guidelines**: Establishes rules for interaction and response patterns
3. **Discord Integration**: Provides Discord-specific formatting and length guidelines
4. **Conversation Rules**: Sets expectations for memory, context, and helpfulness

## Configuration Structure

### JSON Format
```json
{
  "system_prompt": "System instructions text..."
}
```

### Current System Prompt Content
The system prompt establishes the assistant as:
- **Helpful Discord DM Assistant**: Primary role definition
- **Conversational and Friendly**: Tone and interaction style
- **Context-Aware**: Remembers previous conversation messages
- **Discord-Optimized**: Respects platform limits and formatting

## Behavior Guidelines

### Core Instructions
- **Natural Conversation**: Engage in friendly, natural dialogue
- **Helpful and Supportive**: Maintain helpful attitude while being casual
- **Memory Awareness**: Remember and reference previous conversation context
- **Honesty**: Admit when lacking information rather than fabricating

### Response Formatting
- **Character Limits**: Keep responses under 1800 characters for Discord
- **Discord Markdown**: Use **bold** for emphasis when appropriate
- **Readability**: Maintain clear line breaks and structure
- **Conciseness**: Be conversational but not verbose

### Conversation Management
- **Context Retention**: Reference previous messages when relevant
- **Engagement**: Maintain conversational flow and engagement
- **Personalization**: Adapt responses to user's communication style

## Configuration Management

### Loading Process
1. **File Location**: Located in `src/llm/agents/sys_prompts/dm_assistant.json`
2. **Automatic Loading**: Loaded during `DMAssistant` initialization
3. **Error Handling**: Falls back to default prompt if file unavailable
4. **Encoding**: UTF-8 encoding for international character support

### Fallback Behavior
```python
# If JSON loading fails, uses this fallback:
"You are a helpful Discord DM assistant. Be conversational and friendly."
```

## Usage in Agent

### Integration Pattern
```python
class DMAssistant:
    def _load_system_prompt(self) -> str:
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data["system_prompt"]
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            return fallback_prompt
```

### Message Structure Integration
```python
messages = [
    {"role": "system", "content": self.system_prompt},  # Loaded from JSON
    {"role": "user", "content": "Hello!"},
    # ... conversation history
]
```

## Prompt Engineering Considerations

### Discord Platform Optimization
- **Character Awareness**: Mentions 1800 character Discord limit
- **Formatting Guidelines**: Instructs on Discord markdown usage
- **Platform Context**: Acknowledges Discord DM environment

### Conversation Quality
- **Tone Consistency**: Maintains friendly, helpful tone throughout
- **Context Utilization**: Encourages referencing conversation history
- **User Experience**: Focuses on natural, engaging interactions

### Error Prevention
- **Information Boundaries**: Clear instructions about admitting knowledge limits
- **Fabrication Prevention**: Explicitly instructs against making up information
- **Response Length**: Built-in awareness of Discord's technical limitations

## Modification Guidelines

### Safe Prompt Updates
1. **Backup Current**: Save current version before modifications
2. **Test Changes**: Validate with test conversations
3. **Monitor Behavior**: Observe agent responses after updates
4. **Rollback Plan**: Keep working version for quick restoration

### Common Modifications
- **Personality Adjustments**: Modify tone and conversational style
- **Feature Addition**: Add instructions for new capabilities
- **Platform Updates**: Adjust for Discord feature changes
- **User Feedback**: Incorporate user preference insights

## Version Control

### Change Tracking
- **Git History**: Prompt changes tracked in version control
- **Semantic Versioning**: Consider versioning for major prompt changes
- **Change Documentation**: Document reasoning for prompt modifications
- **A/B Testing**: Support for testing multiple prompt variations

### Deployment Strategy
- **No Restart Required**: Prompt changes take effect on agent restart
- **Gradual Rollout**: Test with limited users before full deployment
- **Monitoring**: Track conversation quality after prompt changes

## Current Implementation Status

**JSON Structure**: Fully implemented with proper formatting
**Loading Mechanism**: Fully implemented with error handling
**Fallback Support**: Fully implemented with default prompt
**Integration**: Fully implemented in DMAssistant class
**Error Handling**: Comprehensive error handling for file operations

## Design Decisions

### Why JSON Format?
- **Readability**: Easy for non-developers to read and modify
- **Structure**: Clear separation of different prompt components
- **Extensibility**: Easy to add metadata, versions, or multiple prompts
- **Tooling**: JSON editors provide syntax validation

### Why Separate File?
- **Maintenance**: Prompt updates don't require code changes
- **Version Control**: Track prompt evolution separately from code
- **Collaboration**: Non-technical team members can update prompts
- **Testing**: Easy to test different prompt variations

### Why System Role?
- **LLM Optimization**: System role provides strongest behavior conditioning
- **Conversation Structure**: Clear separation from user/assistant messages
- **Consistency**: Maintains behavior throughout entire conversation

## Integration Points

### File Dependencies
- **Agent Class**: Loaded by `DMAssistant.__init__()`
- **File System**: Requires proper file permissions and encoding
- **Error Recovery**: Integrated with agent's fallback mechanisms

### External Dependencies
- **JSON Module**: Uses Python's built-in JSON parsing
- **File System**: Standard file I/O operations
- **Logging**: Error logging for debugging prompt loading issues

## Future Extensibility

This configuration system supports:
- **Multi-Language Prompts**: Support for different language versions
- **User-Specific Prompts**: Customized prompts per user or group
- **Dynamic Prompts**: Context-aware prompt selection
- **Prompt Templates**: Variable substitution in prompts
- **Metadata Addition**: Version info, creation dates, author information
- **Prompt Analytics**: Tracking prompt effectiveness and user satisfaction

## Best Practices

### Prompt Design
- **Clear Instructions**: Use explicit, unambiguous language
- **Behavior Examples**: Include examples of desired responses
- **Boundary Setting**: Clearly define what the assistant should/shouldn't do
- **Context Awareness**: Include instructions for using conversation history

### File Management
- **Backup Strategy**: Regular backups of working prompts
- **Testing Procedure**: Systematic testing of prompt changes
- **Documentation**: Document the reasoning behind prompt decisions
- **User Feedback**: Incorporate user feedback into prompt improvements
