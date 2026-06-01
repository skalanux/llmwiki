# Skill Registry — llmwiki

Generated: 2026-05-31
Scope: global (user-level) skills

## User-Level Skills

### `~/.agents/skills/`

| Skill | Trigger | Path |
|-------|---------|------|
| code-review | Perform a language-agnostic first-pass code review covering logic errors, bad practices, operation ordering, magic strings, pattern improvements, strict type checking, and SQL injection. | `~/.agents/skills/code-review/SKILL.md` |
| django-patterns | Django architecture patterns, REST API design with DRF, ORM best practices, caching, signals, middleware, and production-grade Django apps. | `~/.agents/skills/django-patterns/SKILL.md` |
| django-tdd | Django testing strategies with pytest-django, TDD methodology, factory_boy, mocking, coverage, and testing Django REST Framework APIs. | `~/.agents/skills/django-tdd/SKILL.md` |
| documentation-writer | Diátaxis Documentation Expert. An expert technical writer specializing in creating high-quality software documentation, guided by the principles and structure of the Diátaxis technical documentation authoring framework. | `~/.agents/skills/documentation-writer/SKILL.md` |
| final-audit | Run a cross-cutting audit across all code produced for a feature. Use when a feature is complete, all PRs are merged, and the user wants a final review for security issues, logic errors, consistency, and best practices. | `~/.agents/skills/final-audit/SKILL.md` |
| find-skills | Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", "is there a skill that can...", or express interest in extending capabilities. | `~/.agents/skills/find-skills/SKILL.md` |
| htmx | HTMX development guidelines for building dynamic web applications with minimal JavaScript using HTML attributes. | `~/.agents/skills/htmx/SKILL.md` |
| issue-to-tasks | Break an issue file into concrete, ordered, AI-executable tasks. | `~/.agents/skills/issue-to-tasks/SKILL.md` |
| prd-to-issues | Break a PRD into independently-grabbable issues using tracer-bullet vertical slices. | `~/.agents/skills/prd-to-issues/SKILL.md` |
| python-code-style | Python code style, linting, formatting, naming conventions, and documentation standards. | `~/.agents/skills/python-code-style/SKILL.md` |
| write-a-prd | Create a PRD through user interview, codebase exploration, and module design, then save it as a file. | `~/.agents/skills/write-a-prd/SKILL.md` |

### `~/.config/opencode/skills/`

| Skill | Trigger | Path |
|-------|---------|------|
| branch-pr | Create Gentle AI pull requests with issue-first checks. | `~/.config/opencode/skills/branch-pr/SKILL.md` |
| chained-pr | Split oversized changes into chained PRs that protect review focus. | `~/.config/opencode/skills/chained-pr/SKILL.md` |
| cognitive-doc-design | Design docs that reduce cognitive load. | `~/.config/opencode/skills/cognitive-doc-design/SKILL.md` |
| comment-writer | Write warm, direct collaboration comments. | `~/.config/opencode/skills/comment-writer/SKILL.md` |
| go-testing | Apply focused Go testing patterns. | `~/.config/opencode/skills/go-testing/SKILL.md` |
| issue-creation | Create Gentle AI issues with issue-first checks. | `~/.config/opencode/skills/issue-creation/SKILL.md` |
| judgment-day | Run blind dual review, fix confirmed issues, then re-judge. | `~/.config/opencode/skills/judgment-day/SKILL.md` |
| skill-creator | Create LLM-first skills with valid frontmatter. | `~/.config/opencode/skills/skill-creator/SKILL.md` |
| skill-improver | Audit and upgrade existing LLM-first skills. | `~/.config/opencode/skills/skill-improver/SKILL.md` |
| work-unit-commits | Plan commits as reviewable work units. | `~/.config/opencode/skills/work-unit-commits/SKILL.md` |

> Note: `sdd-*`, `_shared`, and `skill-registry` skills excluded per registry rules.
> Project-level skills: none detected (empty project).
> Project convention files: none detected.
