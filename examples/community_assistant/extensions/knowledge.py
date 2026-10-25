"""Local JSON knowledge base commands."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from voiceroute import Bot, Context, Extension, command, cooldown

DEFAULT_FAQ_PATH = Path(__file__).parents[1] / "data" / "faq.json"


@dataclass(frozen=True, slots=True)
class FAQEntry:
    slug: str
    title: str
    content: str


class FAQRepository:
    """Load FAQ entries from a user-editable JSON file."""

    def __init__(self, path: Path = DEFAULT_FAQ_PATH) -> None:
        self.path = path

    def load(self) -> tuple[FAQEntry, ...]:
        with self.path.open(encoding="utf-8") as source:
            payload = json.load(source)
        if not isinstance(payload, list):
            raise ValueError("faq.json must contain a list")
        entries: list[FAQEntry] = []
        for raw in payload:
            if not isinstance(raw, dict):
                raise ValueError("each FAQ entry must be an object")
            entries.append(
                FAQEntry(
                    slug=_required_string(raw, "slug"),
                    title=_required_string(raw, "title"),
                    content=_required_string(raw, "content"),
                )
            )
        if len({entry.slug.casefold() for entry in entries}) != len(entries):
            raise ValueError("FAQ slugs must be unique")
        return tuple(entries)


def _required_string(raw: dict[object, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"FAQ field {key!r} must be a non-empty string")
    return value.strip()


class Knowledge(Extension):
    def __init__(self, repository: FAQRepository | None = None) -> None:
        self.repository = repository or FAQRepository()

    @command(
        name="faq",
        description="Показать темы FAQ, ответ или выполнить поиск.",
        usage="[тема | search <запрос>]",
    )
    @cooldown(5, 10.0)
    async def faq(self, context: Context) -> None:
        entries = self.repository.load()
        if not context.args:
            topics = "\n".join(f"• {entry.slug} — {entry.title}" for entry in entries)
            await context.reply(f"Темы FAQ:\n{topics}")
            return

        if context.args[0].casefold() == "search":
            query = " ".join(context.args[1:]).strip()
            if not query:
                await context.reply("Укажите запрос: /faq search <запрос>")
                return
            needle = query.casefold()
            matches = [
                entry
                for entry in entries
                if needle in entry.title.casefold() or needle in entry.content.casefold()
            ]
            if not matches:
                await context.reply("В FAQ ничего не найдено.")
                return
            await context.reply(
                "Найдено в FAQ:\n"
                + "\n".join(f"• {entry.slug} — {entry.title}" for entry in matches)
            )
            return

        topic = " ".join(context.args).casefold()
        entry = next((item for item in entries if item.slug.casefold() == topic), None)
        if entry is None:
            await context.reply("Неизвестная тема FAQ. Используйте /faq для списка.")
            return
        await context.reply(f"{entry.title}\n{entry.content}")


async def setup(bot: Bot) -> Extension:
    return Knowledge()
