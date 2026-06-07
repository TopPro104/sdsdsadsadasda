# ---------------------------------------------------------------------------------
# Name: Typewriter
# Description: Type out a message character-by-character with a running caret
# Author: @Samtakoiiii
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# meta developer: @Samtakoiiii
# scope: hikka_only
# ---------------------------------------------------------------------------------

__version__ = (1, 1, 0)

import asyncio
import html

from herokutl.errors.rpcerrorlist import MessageNotModifiedError

from .. import loader, utils

PUNCT = set(".,!?;:…")


@loader.tds
class TypewriterMod(loader.Module):
    """Type out text character-by-character with a running caret (terminal style)"""

    strings = {
        "name": "Typewriter",
        "no_text": "🚫 <b>Give me text:</b> <code>.type your text</code>",
        "flood": "⏳ <b>FloodWait {}s — raise the</b> <code>delay</code> <b>setting.</b>",
    }

    strings_ru = {
        "no_text": "🚫 <b>Дай текст:</b> <code>.type твой текст</code>",
        "flood": "⏳ <b>FloodWait {}s — подними настройку</b> <code>delay</code><b>.</b>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "delay",
                120,
                "Delay between edits, MILLISECONDS (min 100 to avoid FloodWait)",
                validator=loader.validators.Integer(minimum=100, maximum=3000),
            ),
            loader.ConfigValue(
                "chunk",
                1,
                "Characters added per edit (1 = char-by-char)",
                validator=loader.validators.Integer(minimum=1, maximum=20),
            ),
            loader.ConfigValue(
                "caret",
                "|",
                "Running caret shown after text while typing (empty = none)",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "caret_blink",
                True,
                "Blink the caret on each step (on/off appearance while typing)",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "prefix",
                "",
                "Static prefix printed instantly before typing (e.g. '>>> ')",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "start_delay",
                300,
                "Pause before typing starts, MILLISECONDS",
                validator=loader.validators.Integer(minimum=0, maximum=5000),
            ),
            loader.ConfigValue(
                "punct_pause",
                250,
                "Extra pause after . , ! ? : ; MILLISECONDS (0 = off)",
                validator=loader.validators.Integer(minimum=0, maximum=2000),
            ),
            loader.ConfigValue(
                "end_blink",
                3,
                "Caret blinks at the end (0 = off)",
                validator=loader.validators.Integer(minimum=0, maximum=10),
            ),
            loader.ConfigValue(
                "mode",
                "type",
                "Mode: type / untype / both",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "mono",
                False,
                "Wrap output in monospace (code) formatting",
                validator=loader.validators.Boolean(),
            ),
        )

    def _render(self, text: str, caret: str) -> str:
        body = html.escape(text) + caret
        if self.config["mono"]:
            return f"<code>{body}</code>"
        return body

    async def _edit(self, message, text: str, caret: str) -> bool:
        try:
            await utils.answer(message, self._render(text, caret))
            return True
        except MessageNotModifiedError:
            # identical content (e.g. blinking caret or final state) — not an error
            return True
        except Exception as e:
            wait = getattr(e, "seconds", None)
            if wait:
                await utils.answer(message, self.strings["flood"].format(wait))
                return False
            raise

    async def _sleep_ms(self, ms: int):
        if ms > 0:
            await asyncio.sleep(ms / 1000)

    def _caret_for_step(self, step: int) -> str:
        """Caret that blinks: visible on even steps, hidden on odd (if blink on)."""
        caret = self.config["caret"]
        if not caret:
            return ""
        if self.config["caret_blink"] and step % 2 == 1:
            # keep width stable by using a space instead of the caret
            return " "
        return caret

    async def _type_in(self, message, prefix: str, text: str) -> bool:
        chunk = self.config["chunk"]
        delay = self.config["delay"]
        punct = self.config["punct_pause"]
        step = 0
        for i in range(0, len(text), chunk):
            shown = text[: i + chunk]
            caret = self._caret_for_step(step)
            if not await self._edit(message, prefix + shown, caret):
                return False
            step += 1
            last_char = shown[-1] if shown else ""
            extra = punct if last_char in PUNCT else 0
            await self._sleep_ms(delay + extra)
        return True

    async def _type_out(self, message, prefix: str, text: str) -> bool:
        chunk = self.config["chunk"]
        delay = self.config["delay"]
        caret = self.config["caret"]
        length = len(text)
        for i in range(length, 0, -chunk):
            shown = text[: max(i - chunk, 0)]
            if not await self._edit(message, prefix + shown, caret):
                return False
            await self._sleep_ms(delay)
        return True

    async def _blink_end(self, message, prefix: str, text: str):
        caret = self.config["caret"]
        n = self.config["end_blink"]
        if not (n and caret):
            return
        for _ in range(n):
            await self._edit(message, prefix + text, "")
            await self._sleep_ms(300)
            await self._edit(message, prefix + text, caret)
            await self._sleep_ms(300)

    async def typecmd(self, message):
        """<text> | Type out text with a running caret"""
        text = utils.get_args_raw(message)
        if not text:
            await utils.answer(message, self.strings["no_text"])
            return

        prefix = self.config["prefix"]
        mode = self.config["mode"]
        if mode not in ("type", "untype", "both"):
            mode = "type"
        caret = self.config["caret"]

        # show prefix + caret, pause for drama
        await self._edit(message, prefix, caret)
        await self._sleep_ms(self.config["start_delay"])

        if mode in ("type", "both"):
            if not await self._type_in(message, prefix, text):
                return
            await self._blink_end(message, prefix, text)

        if mode in ("untype", "both"):
            if mode == "untype":
                await self._edit(message, prefix + text, caret)
                await self._sleep_ms(self.config["delay"])
            if not await self._type_out(message, prefix, text):
                return

        # final clean state
        if mode == "type":
            await self._edit(message, prefix + text, "")
        else:
            await self._edit(message, prefix, "")
