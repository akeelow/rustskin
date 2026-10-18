# Blender MCP

Даёт Claude живой доступ к открытому Blender: выполнить Python в сцене
(`execute_blender_code`), посмотреть вьюпорт (`look`), прочитать сцену
(`get_scene_info`). Пакет — [mcp-for-blender](https://github.com/ahujasid/blender-mcp)
2.2.0 (бывший blender-mcp), сервер ставится в `.venv` проекта, а не через uvx.

## Как устроено

```
Claude ⇄ (stdio) .venv/Scripts/mcp-for-blender.exe ⇄ (TCP localhost:9876) аддон в Blender
```

- Конфиг сервера для Claude Code — `.mcp.json` в корне репозитория.
- Аддон — `blender_mcp.py` (копия `blender_mcp/bundled/addon.py` из пакета).
- Телеметрия: сбор промптов/кода/скриншотов выключен по умолчанию (галка
  «Allow Telemetry» в настройках аддона — не включать), анонимная статистика
  отключена через `DISABLE_TELEMETRY=true` в `.mcp.json`.
- Внешние сервисы (Poly Haven, Sketchfab, Hyper3D) по умолчанию выключены — не включаем.
- ⚠️ Сокет без пароля, слушает только `localhost`. `execute_blender_code`
  выполняет любой Python — перед сессией сохраняй свои .blend.

## Каждый раз перед работой

1. Открыть Blender (обычным окном, не `-b`).
2. Во вьюпорте нажать **N** → вкладка **MCP for Blender** → **Start MCP Server**
   (порт 9876).
3. В Claude Code сервер `blender` подхватывается при старте сессии из `.mcp.json`
   (при первом запуске подтвердить).

## Установка на другом компьютере

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
"<путь к blender.exe>" -b -P tools/blender/mcp/install_addon.py
```

Потом поправить путь `command` в `.mcp.json`, если репозиторий лежит не в
`C:/Users/akeel/OneDrive/rustskin`.

Обновление пакета: `.venv/Scripts/pip install -U mcp-for-blender`, затем
скопировать новый `addon.py` в `blender_mcp.py` и снова запустить `install_addon.py`.

## MCP или скрипты?

- **MCP** — интерактивно: собрать сцену, посмотреть, поправить, повторить.
- **Скрипты** (`blender -b -P …`, например `tools/blender/preview.py`) —
  воспроизводимые шаги, которые хранятся в git: рендеры превью, запекание.
  То, что нащупали через MCP, переносим в скрипт.
