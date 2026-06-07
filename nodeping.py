# ---------------------------------------------------------------------------------
# Name: NodePing
# Description: Ping your nodes via TCP connect or HTTP (curl)
# Author: @Samtakoiiii
# ---------------------------------------------------------------------------------
# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
# meta developer: @Samtakoiiii
# scope: hikka_only
# ---------------------------------------------------------------------------------

__version__ = (1, 0, 0)

import asyncio
import time

from .. import loader, utils


async def tcp_check(host: str, port: int, timeout: float):
    start = time.monotonic()
    writer = None
    try:
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        latency = (time.monotonic() - start) * 1000
        return True, latency, f"port {port}"
    except asyncio.TimeoutError:
        return False, None, "timeout"
    except ConnectionRefusedError:
        return False, None, "refused"
    except OSError as e:
        return False, None, str(getattr(e, "strerror", None) or e)[:50]
    except Exception as e:
        return False, None, str(e)[:50]
    finally:
        if writer is not None:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


async def http_check(url: str, timeout: float):
    args = [
        "curl", "-sS", "-o", "/dev/null", "-L", "-m", str(int(timeout)),
        "-w", "%{http_code} %{time_total}", url,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout + 3)
        if proc.returncode != 0:
            return False, None, (err.decode().strip() or f"curl exit {proc.returncode}")[:50]
        parts = out.decode().strip().split()
        code = parts[0] if parts else "???"
        t_ms = float(parts[1]) * 1000 if len(parts) > 1 else None
        ok = code[:1] in ("2", "3")
        return ok, t_ms, f"HTTP {code}"
    except asyncio.TimeoutError:
        return False, None, "timeout"
    except Exception as e:
        return False, None, str(e)[:50]


def parse_node(raw: str):
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 4:
        return None
    name, host, port, kind = parts[0], parts[1], parts[2], parts[3].lower()
    try:
        port = int(port)
    except ValueError:
        port = 0
    if kind not in ("tcp", "http"):
        kind = "tcp"
    return {"name": name, "host": host, "port": port, "kind": kind}


@loader.tds
class NodePingMod(loader.Module):
    """Ping your nodes: TCP connect or HTTP check via curl"""

    strings = {
        "name": "NodePing",
        "no_nodes": "🚫 <b>Node list is empty.</b> Add via <code>.config NodePing</code>",
        "checking": "🛰 <b>Checking {} nodes...</b>",
        "title": "🪐 <b>Nodes status</b>\n\n",
        "row_ok": "🟢 <b>{name}</b> — <code>{lat:.0f}ms</code> <i>({detail})</i>\n",
        "row_bad": "🔴 <b>{name}</b> — <i>{detail}</i>\n",
        "summary": "\n<b>Total:</b> {up}/{total} up",
    }

    strings_ru = {
        "no_nodes": "🚫 <b>Список нод пуст.</b> Добавь через <code>.config NodePing</code>",
        "checking": "🛰 <b>Проверяю {} нод...</b>",
        "title": "🪐 <b>Статус нод</b>\n\n",
        "row_ok": "🟢 <b>{name}</b> — <code>{lat:.0f}ms</code> <i>({detail})</i>\n",
        "row_bad": "🔴 <b>{name}</b> — <i>{detail}</i>\n",
        "summary": "\n<b>Итого:</b> {up}/{total} живых",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "nodes",
                [
                    "Finland|fi.royaltykey.ru|443|tcp",
                    "France|fr.royaltykey.ru|443|tcp",
                    "Germany|de.royaltykey.ru|443|tcp",
                    "Netherlands|nl.royaltykey.ru|443|tcp",
                ],
                "Node list. Format: name|host|port|type (tcp/http)",
                validator=loader.validators.Series(loader.validators.String()),
            ),
            loader.ConfigValue(
                "timeout",
                5,
                "Timeout per check, seconds",
                validator=loader.validators.Integer(minimum=1, maximum=30),
            ),
        )

    async def _check(self, node):
        if node["kind"] == "http":
            ok, lat, detail = await http_check(node["host"], self.config["timeout"])
        else:
            ok, lat, detail = await tcp_check(
                node["host"], node["port"], self.config["timeout"]
            )
        return node, ok, lat, detail

    async def nodescmd(self, message):
        """| Check status of all nodes"""
        nodes = [n for n in (parse_node(r) for r in self.config["nodes"]) if n]

        if not nodes:
            await utils.answer(message, self.strings["no_nodes"])
            return

        await utils.answer(message, self.strings["checking"].format(len(nodes)))

        results = await asyncio.gather(*[self._check(n) for n in nodes])

        text = self.strings["title"]
        up = 0
        for node, ok, lat, detail in results:
            if ok:
                up += 1
                text += self.strings["row_ok"].format(
                    name=node["name"], lat=lat or 0, detail=detail
                )
            else:
                text += self.strings["row_bad"].format(
                    name=node["name"], detail=detail
                )

        text += self.strings["summary"].format(up=up, total=len(nodes))
        await utils.answer(message, text)
