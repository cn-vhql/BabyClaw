import type { ProviderInfo } from "../api/types";
import { isOnlineOnlyMode } from "../api/config";

const ONLINE_ONLY_HIDDEN_PROVIDER_IDS = new Set([
  "ollama",
  "lmstudio",
  "llamacpp",
  "mlx",
]);

export function isProviderHidden(provider: ProviderInfo): boolean {
  if (!isOnlineOnlyMode) {
    return false;
  }

  return (
    provider.is_local || ONLINE_ONLY_HIDDEN_PROVIDER_IDS.has(provider.id)
  );
}

export function filterVisibleProviders(
  providers: ProviderInfo[],
): ProviderInfo[] {
  return providers.filter((provider) => !isProviderHidden(provider));
}
