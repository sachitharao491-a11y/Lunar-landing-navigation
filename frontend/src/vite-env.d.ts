/// <reference types="vite/client" />

declare module "*.glb?url" {
  const assetUrl: string;
  export default assetUrl;
}
