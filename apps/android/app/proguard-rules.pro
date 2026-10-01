# kotlinx.serialization keeps generated serializers via its bundled rules.
# Keep API DTOs' serializer companions explicitly as a safety net.
-keepclassmembers @kotlinx.serialization.Serializable class com.saige.vault.data.** {
    *** Companion;
    kotlinx.serialization.KSerializer serializer(...);
}
