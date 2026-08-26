export type ImageCanvasAddRequest = {
  novelId?: string;
  uri: string;
  previewUri?: string;
  role?: string;
  source: "asset" | "generation";
  assetId?: string;
  filename?: string;
  mediaType?: string;
  size?: number;
  providerId?: string;
  modelId?: string;
};

export const IMAGE_CANVAS_ADD_EVENT = "ai-novel-studio:image-canvas-add";
export function addImageToCanvas(detail: ImageCanvasAddRequest) {
  window.dispatchEvent(
    new CustomEvent<ImageCanvasAddRequest>(IMAGE_CANVAS_ADD_EVENT, { detail }),
  );
}
