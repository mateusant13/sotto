import type { CSSProperties } from "react";

export type Reveal = "fade" | "rise" | "blur" | "type";

export interface CaptionStyle {
  /** tailwind classes for the caption text itself (no background, ever) */
  className: string;
  reveal: Reveal;
  ghostClassName: string;
}

export interface Theme {
  id: string;
  name: string;
  mood: string;
  wallpaper: string;
  swatch: string;
  vars: CSSProperties;
  caption: CaptionStyle;
}

const cap = (
  className: string,
  reveal: Reveal,
  ghostClassName = "font-body font-light"
): CaptionStyle => ({ className, reveal, ghostClassName });

export const THEMES: Theme[] = [
  {
    id: "midnight-rain",
    name: "Midnight Rain",
    mood: "steel blue · the city exhales",
    wallpaper:
      "https://images.pexels.com/photos/35171253/pexels-photo-35171253.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1100&w=1920",
    swatch: "#7fb3dc",
    vars: {
      "--panel": "rgba(9,14,24,0.88)",
      "--panel-2": "rgba(148,180,220,0.06)",
      "--ink": "#e9eff8",
      "--dim": "#93a2b9",
      "--faint": "#5f6d83",
      "--line": "rgba(148,170,200,0.15)",
      "--accent": "#7fb3dc",
      "--accent-ink": "#0a1220",
      "--hover": "rgba(127,179,220,0.10)",
      "--caption-ink": "#f3f7fc",
      "--caption-accent": "#9cc8ec",
      "--scrim": "rgba(4,8,16,0.68)",
      "--shadow": "0 2px 14px rgba(3,7,15,0.65), 0 1px 2px rgba(3,7,15,0.5)",
    } as CSSProperties,
    caption: cap(
      "font-body font-light text-[clamp(20px,2.7vw,31px)] leading-[1.45] text-[var(--caption-ink)]",
      "fade"
    ),
  },
  {
    id: "warm-hour",
    name: "The Warm Hour",
    mood: "amber · diner light, second coffee",
    wallpaper:
      "https://images.pexels.com/photos/34723007/pexels-photo-34723007.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1100&w=1920",
    swatch: "#e0a35f",
    vars: {
      "--panel": "rgba(23,14,9,0.88)",
      "--panel-2": "rgba(230,180,120,0.07)",
      "--ink": "#f7ead9",
      "--dim": "#c2a68c",
      "--faint": "#8a7360",
      "--line": "rgba(230,190,140,0.17)",
      "--accent": "#e0a35f",
      "--accent-ink": "#1c1108",
      "--hover": "rgba(224,163,95,0.12)",
      "--caption-ink": "#faf1e3",
      "--caption-accent": "#ecc08a",
      "--scrim": "rgba(15,7,3,0.68)",
      "--shadow": "0 2px 16px rgba(12,5,1,0.7), 0 1px 2px rgba(12,5,1,0.5)",
    } as CSSProperties,
    caption: cap(
      "font-display italic text-[clamp(21px,2.8vw,33px)] leading-[1.4] text-[var(--caption-ink)]",
      "fade",
      "font-display italic"
    ),
  },
  {
    id: "velvet-dusk",
    name: "Velvet Dusk",
    mood: "dusty rose · the sky won't decide",
    wallpaper:
      "https://images.pexels.com/photos/352882/pexels-photo-352882.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1100&w=1920",
    swatch: "#d18cb2",
    vars: {
      "--panel": "rgba(25,15,24,0.88)",
      "--panel-2": "rgba(220,160,200,0.07)",
      "--ink": "#f4e7f0",
      "--dim": "#bb9ab2",
      "--faint": "#846479",
      "--line": "rgba(220,160,200,0.16)",
      "--accent": "#d18cb2",
      "--accent-ink": "#20101c",
      "--hover": "rgba(209,140,178,0.12)",
      "--caption-ink": "#f9eef6",
      "--caption-accent": "#e6a9c8",
      "--scrim": "rgba(16,7,15,0.66)",
      "--shadow": "0 2px 16px rgba(14,5,13,0.68), 0 1px 2px rgba(14,5,13,0.5)",
    } as CSSProperties,
    caption: cap(
      "font-body font-normal tracking-[0.035em] text-[clamp(19px,2.5vw,29px)] leading-[1.5] text-[var(--caption-ink)]",
      "rise"
    ),
  },
  {
    id: "study-light",
    name: "Study Light",
    mood: "honey · desk lamp, tape hiss",
    wallpaper:
      "https://images.pexels.com/photos/33119680/pexels-photo-33119680.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1100&w=1920",
    swatch: "#d9a45f",
    vars: {
      "--panel": "rgba(20,16,12,0.9)",
      "--panel-2": "rgba(220,190,140,0.06)",
      "--ink": "#f3e8d5",
      "--dim": "#b7a489",
      "--faint": "#7f6f5a",
      "--line": "rgba(220,190,140,0.15)",
      "--accent": "#d9a45f",
      "--accent-ink": "#1a1208",
      "--hover": "rgba(217,164,95,0.12)",
      "--caption-ink": "#f8eeda",
      "--caption-accent": "#e6bb7e",
      "--scrim": "rgba(12,8,4,0.7)",
      "--shadow": "0 2px 14px rgba(10,6,2,0.72), 0 1px 2px rgba(10,6,2,0.5)",
    } as CSSProperties,
    caption: cap(
      "font-mono text-[clamp(16px,2.1vw,24px)] leading-[1.6] text-[var(--caption-ink)]",
      "type"
    ),
  },
  {
    id: "tideline",
    name: "Tideline",
    mood: "seafoam · the moon on water",
    wallpaper:
      "https://images.pexels.com/photos/15406028/pexels-photo-15406028.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1100&w=1920",
    swatch: "#63bfb2",
    vars: {
      "--panel": "rgba(7,18,21,0.88)",
      "--panel-2": "rgba(120,190,180,0.06)",
      "--ink": "#e7f3f1",
      "--dim": "#8fb2ae",
      "--faint": "#5c7874",
      "--line": "rgba(120,190,180,0.16)",
      "--accent": "#63bfb2",
      "--accent-ink": "#07161a",
      "--hover": "rgba(99,191,178,0.11)",
      "--caption-ink": "#f2fbf9",
      "--caption-accent": "#8ed6ca",
      "--scrim": "rgba(3,10,12,0.68)",
      "--shadow": "0 2px 15px rgba(2,9,11,0.7), 0 1px 2px rgba(2,9,11,0.5)",
    } as CSSProperties,
    caption: cap(
      "font-body font-light text-[clamp(20px,2.6vw,30px)] leading-[1.45] text-[var(--caption-ink)]",
      "blur"
    ),
  },
  {
    id: "motel-glow",
    name: "Motel Glow",
    mood: "rose neon · vacancy, no hurry",
    wallpaper:
      "https://images.pexels.com/photos/20856612/pexels-photo-20856612.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1100&w=1920",
    swatch: "#e58fa4",
    vars: {
      "--panel": "rgba(24,12,16,0.89)",
      "--panel-2": "rgba(240,150,175,0.07)",
      "--ink": "#f8e8ec",
      "--dim": "#c09aa6",
      "--faint": "#8a6773",
      "--line": "rgba(240,150,175,0.17)",
      "--accent": "#e58fa4",
      "--accent-ink": "#230d13",
      "--hover": "rgba(229,143,164,0.12)",
      "--caption-ink": "#fdf1f4",
      "--caption-accent": "#f2aebd",
      "--scrim": "rgba(15,6,9,0.7)",
      "--shadow": "0 2px 18px rgba(13,4,7,0.72), 0 0 26px rgba(229,143,164,0.14)",
    } as CSSProperties,
    caption: cap(
      "font-display italic font-medium text-[clamp(22px,3vw,35px)] leading-[1.38] text-[var(--caption-ink)]",
      "fade",
      "font-display italic"
    ),
  },
  {
    id: "paper-moon",
    name: "Paper Moon",
    mood: "silver · monochrome, almost silent",
    wallpaper:
      "https://images.pexels.com/photos/19416468/pexels-photo-19416468.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1100&w=1920",
    swatch: "#aab3c0",
    vars: {
      "--panel": "rgba(240,241,238,0.94)",
      "--panel-2": "rgba(20,24,30,0.045)",
      "--ink": "#191b1f",
      "--dim": "#5f646c",
      "--faint": "#969ba3",
      "--line": "rgba(20,24,30,0.12)",
      "--accent": "#4c5666",
      "--accent-ink": "#f2f3f0",
      "--hover": "rgba(30,40,55,0.07)",
      "--caption-ink": "#f4f6f4",
      "--caption-accent": "#dde2e9",
      "--scrim": "rgba(5,6,10,0.62)",
      "--shadow": "0 2px 14px rgba(0,0,0,0.6), 0 1px 2px rgba(0,0,0,0.45)",
    } as CSSProperties,
    caption: cap(
      "font-mono font-medium uppercase tracking-[0.16em] text-[clamp(14px,1.8vw,20px)] leading-[1.7] text-[var(--caption-ink)]",
      "type"
    ),
  },
  {
    id: "quiet-streets",
    name: "Quiet Streets",
    mood: "lamplight · snow muffles everything",
    wallpaper:
      "https://images.pexels.com/photos/16150134/pexels-photo-16150134.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1100&w=1920",
    swatch: "#92aed4",
    vars: {
      "--panel": "rgba(13,16,23,0.89)",
      "--panel-2": "rgba(150,170,200,0.06)",
      "--ink": "#eaedf3",
      "--dim": "#9ba6b6",
      "--faint": "#67748a",
      "--line": "rgba(150,170,200,0.15)",
      "--accent": "#92aed4",
      "--accent-ink": "#0d1119",
      "--hover": "rgba(146,174,212,0.11)",
      "--caption-ink": "#f4f7fb",
      "--caption-accent": "#aec6e6",
      "--scrim": "rgba(6,8,14,0.68)",
      "--shadow": "0 2px 14px rgba(4,6,12,0.68), 0 1px 2px rgba(4,6,12,0.5)",
    } as CSSProperties,
    caption: cap(
      "font-body font-normal tracking-[0.09em] text-[clamp(18px,2.3vw,27px)] leading-[1.5] text-[var(--caption-ink)]",
      "fade"
    ),
  },
  {
    id: "last-reel",
    name: "Last Reel",
    mood: "gold · analog sunset, end credits",
    wallpaper:
      "https://images.pexels.com/photos/14202029/pexels-photo-14202029.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1100&w=1920",
    swatch: "#d9b36a",
    vars: {
      "--panel": "rgba(24,16,9,0.89)",
      "--panel-2": "rgba(230,190,120,0.07)",
      "--ink": "#f6ebd6",
      "--dim": "#c0a87f",
      "--faint": "#8a7454",
      "--line": "rgba(230,190,120,0.17)",
      "--accent": "#d9b36a",
      "--accent-ink": "#1e1408",
      "--hover": "rgba(217,179,106,0.12)",
      "--caption-ink": "#fbf3df",
      "--caption-accent": "#e8c98c",
      "--scrim": "rgba(14,8,3,0.68)",
      "--shadow": "0 2px 16px rgba(12,6,1,0.7), 0 1px 2px rgba(12,6,1,0.5)",
    } as CSSProperties,
    caption: cap(
      "font-display italic font-medium text-[clamp(21px,2.8vw,32px)] leading-[1.4] text-[var(--caption-ink)]",
      "fade",
      "font-display italic"
    ),
  },
  {
    id: "north-fog",
    name: "North Fog",
    mood: "sage · pines losing their edges",
    wallpaper:
      "https://images.pexels.com/photos/19855997/pexels-photo-19855997.png?auto=compress&cs=tinysrgb&fit=crop&h=1100&w=1920",
    swatch: "#7fbb9c",
    vars: {
      "--panel": "rgba(12,18,15,0.89)",
      "--panel-2": "rgba(140,180,160,0.06)",
      "--ink": "#e9f0ea",
      "--dim": "#98ab9e",
      "--faint": "#64766a",
      "--line": "rgba(140,180,160,0.16)",
      "--accent": "#7fbb9c",
      "--accent-ink": "#0c1310",
      "--hover": "rgba(127,187,156,0.11)",
      "--caption-ink": "#f3faf5",
      "--caption-accent": "#a3d4bb",
      "--scrim": "rgba(5,10,8,0.68)",
      "--shadow": "0 2px 15px rgba(3,8,6,0.7), 0 1px 2px rgba(3,8,6,0.5)",
    } as CSSProperties,
    caption: cap(
      "font-body font-light text-[clamp(20px,2.6vw,30px)] leading-[1.45] text-[var(--caption-ink)]",
      "blur"
    ),
  },
];
