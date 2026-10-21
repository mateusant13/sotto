/**
 * Ten late-night design scenes.
 *
 * Each scene bundles: a cinematic wallpaper (with a colour grade), its own
 * typography, a caption treatment, a panel skin, and a scripted transcript
 * that matches the mood of the place.
 */

export type CaptionVariant = "wide" | "tight" | "italic" | "editorial" | "mono";
export type PanelVariant =
  | "glassCards"
  | "hairline"
  | "paper"
  | "quotes"
  | "ledger"
  | "feed"
  | "bubbles"
  | "timeline"
  | "chips"
  | "gutter";

export interface ScriptLine {
  speaker: string;
  text: string;
}

export interface Scene {
  id: string;
  name: string;
  mood: string;
  place: string;
  hour: string;
  swatch: [string, string];
  wallpaper: string;
  wallFilter: string;
  wallOverlay: string;
  panelWidth: number;
  captionVariant: CaptionVariant;
  captionFont: string;
  caption: {
    color: string;
    dim: string;
    accent: string;
    size: number;
    weight: number;
    leading: number;
    tracking: string;
    transform: "none" | "lowercase";
    shadow: string;
    maxWidth: number;
  };
  panelVariant: PanelVariant;
  panelFont: string;
  panel: {
    surface: string;
    border: string;
    text: string;
    muted: string;
    accent: string;
    soft: string;
    radius: number;
    blur: number;
    shadow: string;
    speaker: Record<string, string>;
  };
  session: {
    title: string;
    note: string;
    source: string;
    device: string;
    lang: string;
    model: string;
  };
  speakers: Record<string, { name: string; role: string }>;
  script: ScriptLine[];
}

const F = {
  inter: "Inter, ui-sans-serif, system-ui, sans-serif",
  news: "Newsreader, Georgia, serif",
  fraunces: "Fraunces, Georgia, serif",
  instrument: "Instrument Serif, Georgia, serif",
  lora: "Lora, Georgia, serif",
  grotesk: "Space Grotesk, ui-sans-serif, sans-serif",
  dm: "DM Mono, ui-monospace, monospace",
  jet: "JetBrains Mono, ui-monospace, monospace",
};

export const scenes: Scene[] = [
  {
    id: "cafe",
    name: "Midnight Café",
    mood: "warm amber · steamed windows",
    place: "A corner café, two espresso cups deep",
    hour: "2:14 AM",
    swatch: ["#E9A85B", "#2A1B12"],
    wallpaper:
      "https://images.pexels.com/photos/776538/pexels-photo-776538.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=1600",
    wallFilter: "saturate(1.06) contrast(1.04) brightness(0.72)",
    wallOverlay:
      "linear-gradient(180deg, rgba(28,17,10,0.62) 0%, rgba(20,13,9,0.34) 46%, rgba(10,7,5,0.86) 100%)",
    panelWidth: 388,
    captionVariant: "wide",
    captionFont: F.news,
    caption: {
      color: "#FCEDD8",
      dim: "rgba(252,237,216,0.34)",
      accent: "#E9A85B",
      size: 34,
      weight: 400,
      leading: 1.34,
      tracking: "-0.012em",
      transform: "none",
      shadow: "0 2px 22px rgba(6,3,1,0.9), 0 1px 2px rgba(0,0,0,0.7)",
      maxWidth: 720,
    },
    panelVariant: "glassCards",
    panelFont: F.inter,
    panel: {
      surface: "rgba(26,18,13,0.52)",
      border: "rgba(255,223,182,0.12)",
      text: "#F6E7D4",
      muted: "rgba(246,231,212,0.5)",
      accent: "#E9A85B",
      soft: "rgba(255,222,180,0.07)",
      radius: 22,
      blur: 20,
      shadow: "0 30px 80px -30px rgba(0,0,0,0.85)",
      speaker: { mara: "#E9A85B", theo: "#B9C9A8" },
    },
    session: {
      title: "Slow Radio · Ep. 41",
      note: "Films that feel like this hour",
      source: "Room microphone",
      device: "mic/02 · built-in",
      lang: "EN",
      model: "murmur-stream v2",
    },
    speakers: {
      mara: { name: "Mara", role: "host" },
      theo: { name: "Theo", role: "guest" },
    },
    script: [
      { speaker: "mara", text: "It's just past two in the morning, and the espresso machine has finally gone quiet." },
      { speaker: "theo", text: "I love it when a room sounds like this. Cups, one radio, nobody in a hurry." },
      { speaker: "mara", text: "Somebody left a paperback on the counter with a receipt from a trip to Lisbon." },
      { speaker: "theo", text: "That's the whole mood right there. Other people's unfinished evenings." },
      { speaker: "mara", text: "Tonight we're talking about films that feel exactly like this hour." },
      { speaker: "theo", text: "Not sad films. Tender ones. The kind you leave feeling strangely forgiven." },
      { speaker: "mara", text: "There's a real difference between melancholy and loneliness, and the good ones know it." },
      { speaker: "theo", text: "They're patient. They let a shot sit longer than you'd expect." },
      { speaker: "mara", text: "Outside it's raining, which helps. Rain is free cinematography." },
      { speaker: "theo", text: "And the lights on the wet asphalt do half the acting for you." },
      { speaker: "mara", text: "If you're listening while folding laundry, that's the correct way to listen." },
      { speaker: "theo", text: "Or driving home the long way. Stay with us, there's more of this." },
    ],
  },
  {
    id: "rainglass",
    name: "Rainglass",
    mood: "cold glass · soft city bokeh",
    place: "A rented flat with the window open a crack",
    hour: "11:48 PM",
    swatch: ["#9FC4D8", "#101A22"],
    wallpaper:
      "https://images.pexels.com/photos/28993171/pexels-photo-28993171.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=1600",
    wallFilter: "saturate(0.86) contrast(1.06) brightness(0.66) hue-rotate(-8deg)",
    wallOverlay:
      "linear-gradient(180deg, rgba(7,13,19,0.64) 0%, rgba(8,14,20,0.32) 50%, rgba(5,9,13,0.88) 100%)",
    panelWidth: 352,
    captionVariant: "tight",
    captionFont: F.inter,
    caption: {
      color: "#E8F1F7",
      dim: "rgba(232,241,247,0.3)",
      accent: "#9FC4D8",
      size: 28,
      weight: 300,
      leading: 1.5,
      tracking: "-0.02em",
      transform: "none",
      shadow: "0 2px 20px rgba(2,6,10,0.92), 0 1px 2px rgba(0,0,0,0.75)",
      maxWidth: 700,
    },
    panelVariant: "hairline",
    panelFont: F.inter,
    panel: {
      surface: "rgba(9,15,21,0.34)",
      border: "rgba(255,255,255,0.09)",
      text: "#E4EDF3",
      muted: "rgba(228,237,243,0.46)",
      accent: "#9FC4D8",
      soft: "rgba(159,196,216,0.06)",
      radius: 14,
      blur: 8,
      shadow: "0 20px 60px -40px rgba(0,0,0,0.9)",
      speaker: { dana: "#9FC4D8", yusuf: "#C7D0C2" },
    },
    session: {
      title: "Night Window · Session 12",
      note: "Ambient field notes",
      source: "Two-channel capture",
      device: "usb/04 · stereo pair",
      lang: "EN",
      model: "murmur-stream v2",
    },
    speakers: {
      dana: { name: "Dana", role: "engineer" },
      yusuf: { name: "Yusuf", role: "recordist" },
    },
    script: [
      { speaker: "dana", text: "Okay, it's running. You can hear the rain on the glass behind us, that's the whole point." },
      { speaker: "yusuf", text: "I usually keep a window open just enough to hear the street below." },
      { speaker: "dana", text: "There's a bus every eleven minutes. I've started timing my tea to it." },
      { speaker: "yusuf", text: "That's a nice rhythm. Trains do the same thing if you live near a line." },
      { speaker: "dana", text: "We're trying to describe why certain sounds help people fall asleep." },
      { speaker: "yusuf", text: "It isn't the sound itself. It's the proof that the world is still out there." },
      { speaker: "dana", text: "Right. Nothing in the room is your responsibility for the next eight hours." },
      { speaker: "yusuf", text: "I recorded this corner once and you could hear a lightbulb humming." },
      { speaker: "dana", text: "I kept that. It's in the last project, about four minutes in." },
      { speaker: "yusuf", text: "Let's let the rain run for a minute and not talk at all." },
      { speaker: "dana", text: "Perfect. We can mark the take and sit still for a while." },
      { speaker: "yusuf", text: "And if the wind clips the microphone, we keep it. It's part of the room." },
    ],
  },
  {
    id: "dustlight",
    name: "Dustlight",
    mood: "1970s film · two-lane dusk",
    place: "Somewhere between towns, windows down",
    hour: "7:32 PM",
    swatch: ["#F0A062", "#3A2114"],
    wallpaper:
      "https://images.pexels.com/photos/27332126/pexels-photo-27332126.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=1600",
    wallFilter: "saturate(1.08) contrast(1.02) sepia(0.14) brightness(0.76)",
    wallOverlay:
      "linear-gradient(180deg, rgba(34,19,11,0.5) 0%, rgba(44,23,14,0.26) 52%, rgba(14,8,5,0.82) 100%)",
    panelWidth: 372,
    captionVariant: "italic",
    captionFont: `${F.fraunces}`,
    caption: {
      color: "#FFE7CC",
      dim: "rgba(255,231,204,0.32)",
      accent: "#F09A55",
      size: 33,
      weight: 400,
      leading: 1.42,
      tracking: "-0.008em",
      transform: "none",
      shadow: "0 2px 22px rgba(24,10,3,0.9), 0 1px 2px rgba(0,0,0,0.65)",
      maxWidth: 740,
    },
    panelVariant: "paper",
    panelFont: F.dm,
    panel: {
      surface: "#F6EDE1",
      border: "rgba(60,40,26,0.14)",
      text: "#35261B",
      muted: "rgba(53,38,27,0.52)",
      accent: "#C4562F",
      soft: "rgba(196,86,47,0.07)",
      radius: 10,
      blur: 0,
      shadow: "0 34px 80px -34px rgba(0,0,0,0.8)",
      speaker: { june: "#B44B27", rail: "#3F5A50" },
    },
    session: {
      title: "Two Lane Highway · Tape 04",
      note: "Roadside log",
      source: "Phone in the cupholder",
      device: "handset/01 · mono",
      lang: "EN",
      model: "murmur-stream v2",
    },
    speakers: {
      june: { name: "June", role: "driver" },
      rail: { name: "Rail", role: "passenger" },
    },
    script: [
      { speaker: "june", text: "It's dusk somewhere outside of nowhere, and the radio only has two stations." },
      { speaker: "rail", text: "I actually like that. It makes the drive feel deliberate." },
      { speaker: "june", text: "There's a sign for a town forty miles away that closes at eight." },
      { speaker: "rail", text: "So nothing to do but watch the sky do the orange thing the whole way." },
      { speaker: "june", text: "This is the part I remember from road trips as a kid. Nobody talking, everybody fine with it." },
      { speaker: "rail", text: "My dad would put on one cassette and let it flip over on its own." },
      { speaker: "june", text: "Side A for the drive out, side B for the drive back." },
      { speaker: "rail", text: "Worth mentioning that the heat is still coming off the asphalt in waves." },
      { speaker: "june", text: "That's the shimmer. It's why those old films look the way they do." },
      { speaker: "rail", text: "Low sun, dust, an engine, and a friend who doesn't need an itinerary." },
      { speaker: "june", text: "We'll stop for coffee in about an hour, if anything is open." },
      { speaker: "rail", text: "If nothing is open, we drink terrible gas station coffee and call it tradition." },
    ],
  },
  {
    id: "analog",
    name: "Analog",
    mood: "cocoa & dust · needle drop",
    place: "Living room, side A ending",
    hour: "10:05 PM",
    swatch: ["#D9A86C", "#2B1D15"],
    wallpaper:
      "https://images.pexels.com/photos/31272472/pexels-photo-31272472.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=1600",
    wallFilter: "saturate(1.02) contrast(1.03) sepia(0.2) brightness(0.74)",
    wallOverlay:
      "radial-gradient(120% 90% at 42% 38%, rgba(58,34,18,0.42) 0%, rgba(20,13,9,0.66) 62%, rgba(12,8,6,0.9) 100%)",
    panelWidth: 378,
    captionVariant: "wide",
    captionFont: F.instrument,
    caption: {
      color: "#FFF2E0",
      dim: "rgba(255,242,224,0.32)",
      accent: "#DCB183",
      size: 36,
      weight: 400,
      leading: 1.3,
      tracking: "-0.01em",
      transform: "none",
      shadow: "0 2px 24px rgba(20,8,2,0.92), 0 1px 2px rgba(0,0,0,0.7)",
      maxWidth: 760,
    },
    panelVariant: "quotes",
    panelFont: F.lora,
    panel: {
      surface: "rgba(32,22,16,0.58)",
      border: "rgba(232,198,155,0.13)",
      text: "#F1E3D3",
      muted: "rgba(241,227,211,0.48)",
      accent: "#D9A86C",
      soft: "rgba(217,168,108,0.07)",
      radius: 18,
      blur: 16,
      shadow: "0 30px 80px -30px rgba(0,0,0,0.85)",
      speaker: { nina: "#D9A86C", abel: "#A9BFA6" },
    },
    session: {
      title: "Vinyl Hour · Sleeve Notes",
      note: "Songs that sound better slightly quieter",
      source: "Turntable + room",
      device: "line/03 · phono pre",
      lang: "EN",
      model: "murmur-stream v2",
    },
    speakers: {
      nina: { name: "Nina", role: "host" },
      abel: { name: "Abel", role: "collector" },
    },
    script: [
      { speaker: "nina", text: "I put this record on by accident and now we're listening to the whole side." },
      { speaker: "abel", text: "That's the nice part. Twenty minutes and you can't really skip it by hand." },
      { speaker: "nina", text: "You'd be surprised. I've become extremely nimble with the tonearm." },
      { speaker: "abel", text: "The crackle is my favourite part, if I'm honest. The room has a texture now." },
      { speaker: "nina", text: "This one came from a shop that smelled like cardboard and coffee." },
      { speaker: "abel", text: "Records remember where you bought them. I can't explain it better than that." },
      { speaker: "nina", text: "Agreed. I can hear the shop, the rain that day, the walk home." },
      { speaker: "abel", text: "Tonight's list is songs that sound better slightly quieter than you want them." },
      { speaker: "nina", text: "Which is essentially every song, if you're patient enough with it." },
      { speaker: "abel", text: "Side two opens with the one your neighbours already know." },
      { speaker: "nina", text: "Let's wait for it. Lift the needle if it skips, don't panic." },
    ],
  },
  {
    id: "shelves",
    name: "Quiet Shelves",
    mood: "green lamplight · paper & rain",
    place: "Reading room, ten minutes after closing",
    hour: "11:41 PM",
    swatch: ["#D8B060", "#141A14"],
    wallpaper:
      "https://images.pexels.com/photos/13278838/pexels-photo-13278838.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=1600",
    wallFilter: "saturate(0.96) contrast(1.07) brightness(0.7)",
    wallOverlay:
      "linear-gradient(180deg, rgba(10,14,10,0.66) 0%, rgba(12,16,12,0.4) 48%, rgba(7,9,7,0.88) 100%)",
    panelWidth: 400,
    captionVariant: "editorial",
    captionFont: F.lora,
    caption: {
      color: "#F2EDDD",
      dim: "rgba(242,237,221,0.3)",
      accent: "#D8B060",
      size: 31,
      weight: 400,
      leading: 1.38,
      tracking: "-0.01em",
      transform: "none",
      shadow: "0 2px 20px rgba(4,6,4,0.92), 0 1px 2px rgba(0,0,0,0.72)",
      maxWidth: 720,
    },
    panelVariant: "ledger",
    panelFont: F.grotesk,
    panel: {
      surface: "rgba(17,21,16,0.6)",
      border: "rgba(216,176,96,0.12)",
      text: "#EDE9DA",
      muted: "rgba(237,233,218,0.46)",
      accent: "#D8B060",
      soft: "rgba(216,176,96,0.06)",
      radius: 6,
      blur: 14,
      shadow: "0 30px 80px -34px rgba(0,0,0,0.88)",
      speaker: { ely: "#D8B060", sam: "#8FAE9C" },
    },
    session: {
      title: "Reading Room · Late Hours",
      note: "Books people read slowly on purpose",
      source: "Table microphone",
      device: "mic/01 · cardioid",
      lang: "EN",
      model: "murmur-stream v2",
    },
    speakers: {
      ely: { name: "Ely", role: "librarian" },
      sam: { name: "Sam", role: "reader" },
    },
    script: [
      { speaker: "ely", text: "It's eleven forty and the library is officially closed, which is the best version of it." },
      { speaker: "sam", text: "The lamplight only reaches about three feet. Everything after that is just books." },
      { speaker: "ely", text: "I've been reading the same paragraph for twenty minutes and I'm not bothered." },
      { speaker: "sam", text: "Some nights you aren't reading. You're just sitting with the sentences." },
      { speaker: "ely", text: "That's it exactly. The book is keeping you company rather than taking you somewhere." },
      { speaker: "sam", text: "There's a draft from the tall window on the west side. I keep meaning to fix it." },
      { speaker: "ely", text: "Leave it. It sounds like pages turning, which is a very good trick." },
      { speaker: "sam", text: "Tonight's list is about letters to someone and essays about weather." },
      { speaker: "ely", text: "Add field guides. You can open one anywhere and feel calm immediately." },
      { speaker: "sam", text: "Yes. Nothing happens except a bird, and it happens beautifully." },
      { speaker: "ely", text: "We'll keep the last one short so you can go home slowly." },
    ],
  },
  {
    id: "lampblack",
    name: "Lamp Black",
    mood: "one lamp · cursor blinking",
    place: "A desk at 1:20 in the morning",
    hour: "1:20 AM",
    swatch: ["#8FA8E8", "#0C0C14"],
    wallpaper:
      "https://images.pexels.com/photos/8036754/pexels-photo-8036754.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=1600",
    wallFilter: "saturate(0.92) contrast(1.08) brightness(0.68) hue-rotate(-6deg)",
    wallOverlay:
      "linear-gradient(205deg, rgba(13,13,23,0.7) 0%, rgba(10,10,17,0.48) 50%, rgba(7,7,13,0.9) 100%)",
    panelWidth: 384,
    captionVariant: "mono",
    captionFont: F.jet,
    caption: {
      color: "#D9DEF0",
      dim: "rgba(217,222,240,0.28)",
      accent: "#8FA8E8",
      size: 24,
      weight: 400,
      leading: 1.6,
      tracking: "-0.01em",
      transform: "lowercase",
      shadow: "0 2px 18px rgba(2,3,8,0.95), 0 1px 2px rgba(0,0,0,0.8)",
      maxWidth: 720,
    },
    panelVariant: "feed",
    panelFont: F.jet,
    panel: {
      surface: "rgba(12,12,20,0.72)",
      border: "rgba(255,255,255,0.075)",
      text: "#CFD6E6",
      muted: "rgba(207,214,230,0.42)",
      accent: "#8FA8E8",
      soft: "rgba(143,168,232,0.07)",
      radius: 12,
      blur: 18,
      shadow: "0 30px 80px -32px rgba(0,0,0,0.9)",
      speaker: { ari: "#8FA8E8", jo: "#C8A98F" },
    },
    session: {
      title: "Desk, 1:20 AM · Workspace Audio",
      note: "Logged as ambient",
      source: "Laptop microphone",
      device: "mic/02 · built-in",
      lang: "EN",
      model: "murmur-stream v2",
    },
    speakers: {
      ari: { name: "Ari", role: "writer" },
      jo: { name: "Jo", role: "editor" },
    },
    script: [
      { speaker: "ari", text: "It's one in the morning and the only thing awake in here is the lamp." },
      { speaker: "jo", text: "Plus the cursor. It's been blinking at the same sentence for an hour." },
      { speaker: "ari", text: "I've decided that's productive. The sentence is getting warmer." },
      { speaker: "jo", text: "Let's log tonight as ambient. Typing, rain, the kettle once." },
      { speaker: "ari", text: "The kettle is a key event in this house. It's basically the intermission." },
      { speaker: "jo", text: "I like the small sounds. A shut drawer. A chair that gives in a little." },
      { speaker: "ari", text: "That's why I record here and not in a studio. Everything sounds lived in." },
      { speaker: "jo", text: "Take a break in a second and let the room talk for a while." },
      { speaker: "ari", text: "I'll stop narrating my own life for at least ninety seconds." },
      { speaker: "jo", text: "Good. Then we finish the paragraph and go to bed, in that order." },
      { speaker: "ari", text: "Reasonable. Turn the lamp down halfway and we're done." },
    ],
  },
  {
    id: "rooftop",
    name: "Rooftop Dusk",
    mood: "periwinkle · dinner smells",
    place: "Six floors up, towels still on the line",
    hour: "8:12 PM",
    swatch: ["#E4B0CC", "#1C1630"],
    wallpaper:
      "https://images.pexels.com/photos/13912167/pexels-photo-13912167.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=1600",
    wallFilter: "saturate(0.98) contrast(1.02) brightness(0.74)",
    wallOverlay:
      "linear-gradient(180deg, rgba(28,22,46,0.6) 0%, rgba(38,28,52,0.28) 52%, rgba(14,11,22,0.86) 100%)",
    panelWidth: 366,
    captionVariant: "italic",
    captionFont: F.lora,
    caption: {
      color: "#F3E9F4",
      dim: "rgba(243,233,244,0.3)",
      accent: "#E4B0CC",
      size: 30,
      weight: 400,
      leading: 1.42,
      tracking: "-0.008em",
      transform: "none",
      shadow: "0 2px 20px rgba(8,4,16,0.9), 0 1px 2px rgba(0,0,0,0.66)",
      maxWidth: 720,
    },
    panelVariant: "bubbles",
    panelFont: F.inter,
    panel: {
      surface: "rgba(29,23,42,0.56)",
      border: "rgba(240,222,246,0.12)",
      text: "#F0E9F2",
      muted: "rgba(240,233,242,0.48)",
      accent: "#E4B0CC",
      soft: "rgba(228,176,204,0.08)",
      radius: 20,
      blur: 18,
      shadow: "0 30px 80px -32px rgba(0,0,0,0.85)",
      speaker: { mina: "#E4B0CC", cole: "#A9C0E0" },
    },
    session: {
      title: "Upstairs · Dusk Sessions",
      note: "Two songs this exact colour",
      source: "Wireless lapel",
      device: "lav/01 · mono",
      lang: "EN",
      model: "murmur-stream v2",
    },
    speakers: {
      mina: { name: "Mina", role: "host" },
      cole: { name: "Cole", role: "guest" },
    },
    script: [
      { speaker: "mina", text: "We got up here just in time. The sky is doing the thing between blue and gold." },
      { speaker: "cole", text: "And the whole city is making dinner noise. Plates, one scooter, a distant conversation." },
      { speaker: "mina", text: "Birds keep crossing in groups. I think it's their commute." },
      { speaker: "cole", text: "This is my favourite half hour. Everything is still negotiable." },
      { speaker: "mina", text: "You can't see it in the recording, but the rooftops are all slightly different colours." },
      { speaker: "cole", text: "Somebody two buildings over is watering plants in a bathrobe. Very peaceful." },
      { speaker: "mina", text: "That's the vibe tonight. Neighbours being neighbours, happily far away." },
      { speaker: "cole", text: "We'll play two songs that sound like this exact colour of sky." },
      { speaker: "mina", text: "Then we let the street take over until the lights come on." },
      { speaker: "cole", text: "There goes the first one. Somebody in the building across is making soup." },
      { speaker: "mina", text: "Good for them. We'll be right here with the towel line." },
    ],
  },
  {
    id: "tideline",
    name: "Tideline",
    mood: "graphite sea · long exposure",
    place: "A cold shore, mist eating the horizon",
    hour: "9:56 PM",
    swatch: ["#9CC3CC", "#0E1418"],
    wallpaper:
      "https://images.pexels.com/photos/33401396/pexels-photo-33401396.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=1600",
    wallFilter: "saturate(0.84) contrast(1.06) brightness(0.68) hue-rotate(-4deg)",
    wallOverlay:
      "linear-gradient(180deg, rgba(9,14,17,0.62) 0%, rgba(11,17,20,0.34) 50%, rgba(5,8,10,0.88) 100%)",
    panelWidth: 350,
    captionVariant: "wide",
    captionFont: F.news,
    caption: {
      color: "#E7EFF3",
      dim: "rgba(231,239,243,0.28)",
      accent: "#9CC3CC",
      size: 32,
      weight: 300,
      leading: 1.4,
      tracking: "-0.014em",
      transform: "none",
      shadow: "0 2px 20px rgba(2,6,8,0.94), 0 1px 2px rgba(0,0,0,0.75)",
      maxWidth: 700,
    },
    panelVariant: "timeline",
    panelFont: F.inter,
    panel: {
      surface: "rgba(13,19,23,0.5)",
      border: "rgba(190,214,220,0.1)",
      text: "#DFE9ED",
      muted: "rgba(223,233,237,0.44)",
      accent: "#9CC3CC",
      soft: "rgba(156,195,204,0.06)",
      radius: 16,
      blur: 12,
      shadow: "0 30px 80px -36px rgba(0,0,0,0.88)",
      speaker: { ivo: "#9CC3CC", nora: "#C6C2AE" },
    },
    session: {
      title: "Low Tide · Field Take 7",
      note: "Two minutes in, most people are asleep",
      source: "Rocks, 8 metres out",
      device: "field/02 · shock mount",
      lang: "EN",
      model: "murmur-stream v2",
    },
    speakers: {
      ivo: { name: "Ivo", role: "recordist" },
      nora: { name: "Nora", role: "producer" },
    },
    script: [
      { speaker: "ivo", text: "Listen to that. The waves aren't big tonight, they're just breathing." },
      { speaker: "nora", text: "The mist is thick enough that the horizon has basically given up." },
      { speaker: "ivo", text: "I like when the sea stops pretending to be dramatic and just keeps time." },
      { speaker: "nora", text: "We've got the mics down near the rocks, so you'll hear the small stuff too." },
      { speaker: "ivo", text: "Water finding a gap, then letting go of it. Very patient." },
      { speaker: "nora", text: "This is the part people put on to fall asleep. Two minutes in, gone." },
      { speaker: "ivo", text: "I understand it. It's the least demanding sound in the world." },
      { speaker: "nora", text: "Nothing to understand, nothing to answer. A very slow metronome." },
      { speaker: "ivo", text: "We'll leave the recording running for the walk back along the shore." },
      { speaker: "nora", text: "If the wind reaches the microphone, apologies. It's part of the deal." },
      { speaker: "ivo", text: "Take the headphones off for a second and just hear it." },
    ],
  },
  {
    id: "ember",
    name: "Ember",
    mood: "stove warm · snow sideways",
    place: "A cabin where nobody suggests a plan",
    hour: "10:47 PM",
    swatch: ["#F08A4B", "#180D0A"],
    wallpaper:
      "https://images.pexels.com/photos/7245418/pexels-photo-7245418.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=1600",
    wallFilter: "saturate(1.06) contrast(1.08) brightness(0.7)",
    wallOverlay:
      "radial-gradient(110% 80% at 50% 88%, rgba(196,84,26,0.34) 0%, rgba(30,14,9,0.6) 52%, rgba(10,6,5,0.92) 100%)",
    panelWidth: 396,
    captionVariant: "editorial",
    captionFont: F.fraunces,
    caption: {
      color: "#FFE4CE",
      dim: "rgba(255,228,206,0.3)",
      accent: "#F08A4B",
      size: 32,
      weight: 400,
      leading: 1.38,
      tracking: "-0.01em",
      transform: "none",
      shadow: "0 2px 22px rgba(20,6,1,0.92), 0 1px 2px rgba(0,0,0,0.7)",
      maxWidth: 720,
    },
    panelVariant: "chips",
    panelFont: F.inter,
    panel: {
      surface: "rgba(24,14,11,0.66)",
      border: "rgba(255,196,150,0.12)",
      text: "#F6E0D2",
      muted: "rgba(246,224,210,0.46)",
      accent: "#F08A4B",
      soft: "rgba(240,138,75,0.08)",
      radius: 14,
      blur: 16,
      shadow: "0 30px 80px -30px rgba(0,0,0,0.88)",
      speaker: { willow: "#F08A4B", tan: "#A8B79B" },
    },
    session: {
      title: "Stove, Snowfall · Cabin Log 3",
      note: "All wood split this afternoon",
      source: "Stove-side microphone",
      device: "mic/05 · warm",
      lang: "EN",
      model: "murmur-stream v2",
    },
    speakers: {
      willow: { name: "Willow", role: "host" },
      tan: { name: "Tan", role: "guest" },
    },
    script: [
      { speaker: "willow", text: "It's snowing sideways and the stove is doing most of the talking tonight." },
      { speaker: "tan", text: "There's something honest about a fire. It doesn't try to sound nice." },
      { speaker: "willow", text: "We split wood all afternoon, so we've earned this one." },
      { speaker: "tan", text: "The kettle is on the left burner. In a minute it'll add a second sound." },
      { speaker: "willow", text: "This is the kind of evening where nobody suggests a plan." },
      { speaker: "tan", text: "Correct. Plans are for weather you can actually walk in." },
      { speaker: "willow", text: "I keep thinking about that film where nothing happens and someone makes soup." },
      { speaker: "tan", text: "Perfect movie. It's basically a documentary about being warm." },
      { speaker: "willow", text: "Let's end with the wind down the chimney. It does the outro for us." },
      { speaker: "tan", text: "And if you're driving in this, slow down. We'll be here when you get back." },
      { speaker: "willow", text: "Doors are unlocked, kettle's warm, no plan until morning." },
    ],
  },
  {
    id: "fieldnotes",
    name: "Field Notes",
    mood: "after the storm · birds on wires",
    place: "Balcony, east-facing, second cup of tea",
    hour: "6:58 AM",
    swatch: ["#4E6E70", "#F2EDE2"],
    wallpaper:
      "https://images.pexels.com/photos/9038490/pexels-photo-9038490.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=900&w=1600",
    wallFilter: "saturate(0.92) contrast(1.04) brightness(0.8)",
    wallOverlay:
      "linear-gradient(180deg, rgba(17,27,32,0.62) 0%, rgba(19,29,34,0.32) 50%, rgba(10,16,19,0.88) 100%)",
    panelWidth: 414,
    captionVariant: "tight",
    captionFont: F.inter,
    caption: {
      color: "#F3F0E8",
      dim: "rgba(243,240,232,0.3)",
      accent: "#A9CBC6",
      size: 27,
      weight: 300,
      leading: 1.52,
      tracking: "-0.018em",
      transform: "none",
      shadow: "0 2px 20px rgba(3,7,9,0.92), 0 1px 2px rgba(0,0,0,0.7)",
      maxWidth: 700,
    },
    panelVariant: "gutter",
    panelFont: F.news,
    panel: {
      surface: "rgba(243,239,230,0.94)",
      border: "rgba(35,45,48,0.12)",
      text: "#232A2C",
      muted: "rgba(35,42,44,0.5)",
      accent: "#3F5E60",
      soft: "rgba(63,94,96,0.07)",
      radius: 16,
      blur: 0,
      shadow: "0 34px 80px -34px rgba(0,0,0,0.75)",
      speaker: { rui: "#3F5E60", ada: "#9C5F45" },
    },
    session: {
      title: "Morning After · Notes 02",
      note: "Storm passed around four",
      source: "Kitchen counter",
      device: "handset/02 · mono",
      lang: "EN",
      model: "murmur-stream v2",
    },
    speakers: {
      rui: { name: "Rui", role: "host" },
      ada: { name: "Ada", role: "guest" },
    },
    script: [
      { speaker: "rui", text: "So the storm passed around four, and everything smells like wet pavement now." },
      { speaker: "ada", text: "I woke up to birds arguing about who gets the wire." },
      { speaker: "rui", text: "They're the loudest thing in the recording. Somehow it still feels quiet." },
      { speaker: "ada", text: "That's the trick. It's all background, even the arguments." },
      { speaker: "rui", text: "We're going through the notes you left on the kitchen table." },
      { speaker: "ada", text: "One of them just says ask about the balcony, so here we are." },
      { speaker: "rui", text: "Considered asked. What about the balcony?" },
      { speaker: "ada", text: "It faces east, so light gets in around six and stays gentle until eight." },
      { speaker: "rui", text: "That's honestly the whole reason we moved here. That hour." },
      { speaker: "ada", text: "Noted. Let's finish this before the traffic starts." },
      { speaker: "rui", text: "Deal. Tea first, then we walk to the corner and back." },
    ],
  },
];

export const formatClock = (ms: number) => {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
};

export const formatShort = (ms: number) => {
  const total = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
};

export const countWords = (segments: { text: string }[]) =>
  segments.reduce((sum, s) => sum + s.text.trim().split(/\s+/).filter(Boolean).length, 0);
