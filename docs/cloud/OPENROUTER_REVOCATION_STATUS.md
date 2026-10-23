# OpenRouter revocation status

23 October 2026: **revocation is not confirmed**. The credential was cleared
from the current tracked company configuration in commit `d678256`; earlier
Git history still contains it. It must be treated as compromised.

No OpenRouter account connector, authenticated browser session, management-key
binding or relevant credential environment variable is available in this
machine. No credentials were recovered from history or used for inference.

OpenRouter's official Python SDK documents that key deletion requires a
management key and the target key's hash identifier. This was verified from
the official repository at commit
`f2af2b8de9b03bdc1a4d449d9f8d6502631dcba9`:
[APIKeys.delete](https://github.com/OpenRouterTeam/python-sdk/blob/f2af2b8de9b03bdc1a4d449d9f8d6502631dcba9/src/openrouter/api_keys.py#L894).
An exposed inference key is not proof that account-management access exists.

The account owner should delete the exposed key at
[OpenRouter Keys](https://openrouter.ai/settings/keys) and check recent usage.
Do not paste a key into chat. The local evidence/research workflow does not
need a replacement OpenRouter key. Record provider confirmation before marking
this incident revoked; clearing a file or saving network settings is insufficient.
