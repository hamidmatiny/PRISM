import { defineStore } from "pinia";
import { ref } from "vue";

export const useSelectionStore = defineStore("selection", () => {
  const selectedAssetId = ref<string | null>(null);
  const panelOpen = ref(false);

  function select(assetId: string | null): void {
    selectedAssetId.value = assetId;
    panelOpen.value = Boolean(assetId);
  }

  function closePanel(): void {
    panelOpen.value = false;
  }

  return { selectedAssetId, panelOpen, select, closePanel };
});
