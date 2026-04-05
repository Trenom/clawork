# Contributing to Clawork

We're excited that you want to contribute to Clawork! This document explains how to get involved.

---

## Code of Conduct

This project is committed to providing a welcoming and inclusive environment for all contributors, regardless of background, experience level, or identity.

### Expected Behavior

- Be respectful and professional
- Welcome diverse perspectives
- Give credit where due
- Assume good faith
- Provide constructive feedback

### Unacceptable Behavior

- Harassment, discrimination, or intimidation
- Deliberate misinformation
- Spamming or malicious activity
- Anything that violates applicable laws

**Report violations** to the maintainers privately. We take these seriously.

---

## Getting Started

### Prerequisites

- Git installed
- Claude Cowork running
- Basic familiarity with Clawork (read README.md and setup guide)
- Python 3 (for import scripts)
- Bash (for shell scripts)

### Set Up Your Development Environment

```bash
# Clone the repository
git clone https://github.com/anthropic-labs/clawork.git
cd clawork

# Create a feature branch
git checkout -b feature/your-feature-name

# Make your changes
# Test thoroughly
# Commit and push
```

---

## Types of Contributions

### Bug Reports

**Found a bug?** Create an issue with:

1. **Title**: Clear, concise description
2. **Environment**: Your OS, Cowork version, Clawork version
3. **Steps to reproduce**: Exact steps to trigger the bug
4. **Expected behavior**: What should happen
5. **Actual behavior**: What actually happens
6. **Logs**: Relevant output from `~/claw/logs/`
7. **Screenshots**: If visual issue

**Example**:
```
Title: WhatsApp messages not being read from web.whatsapp.com

Environment:
- OS: macOS 13.2
- Cowork version: 0.5.0
- Clawork commit: abc1234

Steps:
1. Set up Clawork with WhatsApp enabled
2. Send message from phone to web.whatsapp.com account
3. Wait for heartbeat cycle
4. Check ~/claw/inbox/

Expected: Ticket should be created with message content
Actual: No ticket created; heartbeat.jsonl shows "no messages found"

Logs:
[paste relevant error from logs]
```

### Feature Requests

**Want a new feature?** Open an issue with:

1. **Problem**: What problem does this solve?
2. **Solution**: Your proposed approach
3. **Use cases**: Who would use this and when?
4. **Alternatives**: What else did you consider?

**Example**:
```
Title: Support for Discord as message channel

Problem: Many teams use Discord for communication. Clawork only supports WhatsApp, Telegram, Slack, and Gmail.

Proposed Solution:
Add Discord connector using Python discord.py library. Create new skill clawork-discord that mirrors clawork-messenger behavior but for Discord channels.

Use Cases:
- DevOps teams that use Discord
- Game development communities
- Open source projects

This would expand Clawork's applicability to communities where Discord is primary communication tool.
```

### Documentation Improvements

**Better docs help everyone.** You can:

- Fix typos or grammar
- Clarify confusing sections
- Add examples
- Translate to other languages
- Improve organization
- Add troubleshooting steps

**No issue needed** — just submit a PR with your changes.

### Code Contributions

**Adding features or fixing bugs?** See the [Development Guide](#development-guide) section.

### Testing & QA

**Help us test:**

1. Try Clawork in different environments (Mac, Linux, WSL2)
2. Test with different channel combinations
3. Try unusual configurations
4. Report edge cases you discover
5. Provide feedback on documentation clarity

---

## Development Guide

### Code Style

#### Python (import scripts)

- Follow PEP 8
- Use 4 spaces for indentation
- Use type hints where helpful
- Write docstrings for functions

```python
def import_openclaw_config(openclaw_path: str) -> dict:
    """Import configuration from OpenClaw.

    Args:
        openclaw_path: Path to openclaw.json file

    Returns:
        Dictionary of Clawork configuration

    Raises:
        FileNotFoundError: If openclaw.json doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    # Implementation here
    pass
```

#### Shell (setup scripts)

- Use #!/bin/bash shebang
- Exit on error: `set -e`
- Use meaningful variable names
- Quote variables: `"$var"`
- Add helpful echo output

```bash
#!/bin/bash
set -e

CLAW_HOME="${CLAW_HOME:-$HOME/claw}"

echo "Creating directory: $CLAW_HOME"
mkdir -p "$CLAW_HOME"/{inbox,outbox}

if [ -f "$CONFIG_FILE" ]; then
    echo "Config file exists"
else
    echo "Warning: Config file not found"
fi
```

#### Markdown (documentation)

- Use clear, active voice
- Break content into logical sections
- Include code examples
- Use backticks for inline code
- Use triple backticks with language for code blocks
- Include explanatory comments

### Skills Development

New skills should follow this structure:

```markdown
# skill-name — Brief description

What this skill does.

## Activation

When this skill is invoked.

## Responsibilities

What it's responsible for.

## Input

Expected ticket format and fields used.

## Process

Step-by-step pseudocode of logic.

## Output

What gets written to ticket.result.

## Integration Points

Other skills or components it depends on.
```

### Testing Your Code

#### Manual Testing Checklist

```markdown
## Test Case: [Description]

1. Set up scenario
   [ ] Step 1
   [ ] Step 2

2. Execute
   [ ] Action 1
   [ ] Action 2

3. Verify
   [ ] Expected result 1
   [ ] Expected result 2

4. Clean up
   [ ] Remove test data
```

#### Example Test

```markdown
## Test: Router routes messages by content

1. Setup
   [ ] Create test ticket with instruction="needs order info"
   [ ] Config has rule: content_contains="order" → skill="order-agent"

2. Execute
   [ ] Invoke router with test ticket

3. Verify
   [ ] Check ticket.routing.target_skill == "order-agent"
   [ ] Check routing was logged to router.jsonl

4. Clean up
   [ ] Delete test ticket files
```

### Commit Messages

Write clear, descriptive commit messages:

```
Short summary (50 chars max)

Longer explanation if needed (wrap at 72 chars).
Explain why you made this change, not just what.

Fixes #123 (if fixing an issue)
Co-authored-by: Name <email> (if paired)
```

**Examples**:
```
Fix WhatsApp message reader not finding chats

The message reader was searching for incorrect CSS selector
after WhatsApp Web UI update. Updated selector to match
current layout. Added test case to prevent regression.

Fixes #456

---

Add session compaction logic

Large sessions were consuming excessive context tokens.
Implement automatic summarization when session exceeds
threshold. Old messages are summarized, recent messages
are preserved for maximum relevance.

---

Improve config reference documentation

Added detailed field descriptions, examples, and
troubleshooting tips for every configuration option.
Reorganized into logical sections.
```

### Creating a Pull Request

1. **Fork the repository** (if you don't have write access)
2. **Create a feature branch**: `git checkout -b feature/my-feature`
3. **Make your changes**
4. **Write tests** for new functionality
5. **Update documentation** if needed
6. **Commit with clear messages**
7. **Push to your fork**
8. **Create Pull Request** with description

**PR Template**:
```markdown
## Description
Brief summary of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Refactoring

## Testing Done
[ ] Manual testing
[ ] Added tests
[ ] Tested in multiple environments

## Documentation Updated
- [ ] README.md
- [ ] docs/
- [ ] Code comments
- [ ] CHANGELOG.md

## Screenshots (if UI change)
[If applicable, add screenshots]

## Checklist
- [ ] My code follows the style guidelines
- [ ] I've added tests for new functionality
- [ ] All tests pass locally
- [ ] Documentation is updated
- [ ] No breaking changes (or documented)
```

---

## Review Process

### What Reviewers Will Check

1. **Correctness**: Does it do what it claims?
2. **Quality**: Is it well-written and maintainable?
3. **Testing**: Is it adequately tested?
4. **Documentation**: Is it documented?
5. **Compatibility**: Does it work with existing code?
6. **Performance**: Does it introduce any regressions?

### How to Respond to Feedback

- Be open to suggestions
- Ask clarifying questions if feedback is unclear
- Provide context for design decisions
- Make requested changes or explain why you can't
- Re-request review after making changes

### Approval & Merge

Once 2+ reviewers approve and CI passes, a maintainer will merge.

---

## Project Structure Guide

```
clawork/
├── README.md               ← Start here
├── CONTRIBUTING.md         ← This file
├── LICENSE                 ← MIT license
│
├── docs/                   ← Documentation (read these!)
│   ├── architecture.md     ← System design
│   ├── config-reference.md ← Config options
│   ├── ticket-protocol.md  ← Ticket format
│   ├── migration.md        ← From OpenClaw
│   └── setup-guide.md      ← Getting started
│
├── skills/                 ← Core skills
│   ├── clawork-soul/       ← Agent personality
│   ├── clawork-router/     ← Routing engine
│   └── clawork-sessions/   ← Session management
│
├── config/
│   └── config.example.yaml ← Example config
│
├── scripts/                ← Setup & utilities
│   ├── setup.sh            ← Initialize Clawork
│   └── import-openclaw-config.sh
│
├── templates/              ← Example files
│   ├── ticket.example.json
│   ├── session.example.jsonl
│   └── heartbeat-prompt.md
│
└── tests/                  ← Test documentation
    └── test-scenarios.md   ← Manual test cases
```

---

## Areas Looking for Help

### High Priority

- [ ] Phase 2: clawork-messenger skill (WhatsApp/Telegram automation)
- [ ] Documentation for Windows/WSL2 setup
- [ ] Performance benchmarking and optimization
- [ ] End-to-end test suite

### Medium Priority

- [ ] Additional language support (docs in other languages)
- [ ] Integration examples with popular tools
- [ ] Configuration templates for common use cases
- [ ] Video tutorials and screen recordings

### Nice to Have

- [ ] Web-based configuration UI
- [ ] Analytics dashboard
- [ ] Message templates library
- [ ] Community skill sharing platform

---

## Release Process

We follow semantic versioning: MAJOR.MINOR.PATCH

### Release Checklist

- [ ] All PRs merged and tested
- [ ] CHANGELOG.md updated
- [ ] Version bumped in relevant files
- [ ] README.md updated if needed
- [ ] Git tag created: v1.2.3
- [ ] GitHub release published with notes
- [ ] Announcement posted

### Versioning

- **MAJOR** (1.0.0): Breaking changes, major new features
- **MINOR** (0.1.0): New features, backward compatible
- **PATCH** (0.0.1): Bug fixes, documentation

---

## Getting Help

### Questions?

- Check **docs/** first
- Search **GitHub Issues** for similar questions
- Ask in **GitHub Discussions**
- Reach out to maintainers

### Stuck?

- Review the **troubleshooting** docs
- Check **logs** in `~/claw/logs/`
- Create a detailed **issue** with reproducible steps
- Ask for **help** in Discussions (not required for issues)

---

## Maintainers

The Clawork project is maintained by:

- **Lead Maintainer**: [Name] (@username)
- **Contributors**: [List of significant contributors]

Contact maintainers via:
- GitHub Issues (public)
- GitHub Discussions (public)
- Email (private, if needed)

---

## Thanks

Contributing to open source takes time and effort. We truly appreciate your:

- **Bug reports** that make Clawork more reliable
- **Feature requests** that expand possibilities
- **Code contributions** that improve functionality
- **Documentation improvements** that help everyone
- **Bug fixes** that solve problems
- **Testing** that catches issues
- **Feedback** that shapes direction
- **Kindness** in the community

**Every contribution matters.** Thank you for being part of the Clawork community.

---

## Additional Resources

- [GitHub Help](https://help.github.com)
- [Git Documentation](https://git-scm.com/doc)
- [Markdown Guide](https://www.markdownguide.org)
- [Semantic Versioning](https://semver.org)
- [Keep a Changelog](https://keepachangelog.com)

---

**Happy contributing!**

If you have suggestions for improving this document, please open an issue or PR.