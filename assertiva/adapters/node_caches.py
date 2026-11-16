"""Caches JavaScript tooling writes inside node_modules.

Vite and Vitest default to node_modules/.vite (dependency pre-bundling, results), Vitest may use
node_modules/.vitest, and many tools use node_modules/.cache. When node_modules is linked into a
disposable copy, these writes would land in the audited project; Node adapters declare them so the
copy keeps them local (see ``evidence.local_cache_entries`` and ``workspace.link_installed``).
"""

NODE_TOOL_CACHE_ENTRIES: tuple[str, ...] = (".vite", ".vitest", ".cache", ".vite-temp")
