"""Provider-independent AI interfaces for Saige Vault.

Concrete providers (Anthropic, OpenAI, Google, Ollama, Tesseract...) are
implemented in later phases behind these protocols. Application code depends
only on the protocols, never on a vendor SDK.
"""

__version__ = "0.1.0"
