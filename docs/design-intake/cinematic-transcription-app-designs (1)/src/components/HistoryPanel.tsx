import type { ComponentType } from "react";
import type { PanelVariant } from "@/data/scenes";
import { panelSetA } from "./panels/PanelSetA";
import { panelSetB } from "./panels/PanelSetB";
import type { PanelProps } from "./panels/shared";

const registry: Record<PanelVariant, ComponentType<PanelProps>> = {
  ...panelSetA,
  ...panelSetB,
};

/** Right-hand history rail. Ten skins, one data contract. */
export function HistoryPanel(props: PanelProps) {
  const Skin = registry[props.scene.panelVariant] ?? panelSetA.glassCards;
  return <Skin {...props} />;
}
