export interface Line {
  speaker: string;
  text: string;
}

export interface Script {
  id: string;
  title: string;
  sampleRateNote: string;
  lines: Line[];
}

export const SPEAKER_INITIALS: Record<string, string> = {
  June: "JU",
  Marlow: "MA",
  "Sofia (caller)": "SO",
  Alun: "AL",
  Cleo: "CL",
  "Dr. Vasquez": "DV",
  Toma: "TO",
  Ines: "IN",
  Reader: "RD",
  Host: "HO",
  Pia: "PI",
};

const short = (name: string) => (name.includes("(") ? name.split(" (")[0] : name);

export const SCRIPTS: Script[] = [
  {
    id: "late-radio",
    title: "Late Shift Radio",
    sampleRateNote: "studio condenser · 48 kHz",
    lines: [
      { speaker: "June", text: "You're on the night shift with me and it's just gone quarter past one." },
      { speaker: "Marlow", text: "Which means the calls are about to get honest, that's how it always goes." },
      { speaker: "June", text: "Every week. Twelve to two and people start telling me the truth about their kitchens." },
      { speaker: "Marlow", text: "I still think about the man who called about the kettle he kept in the garage." },
      { speaker: "June", text: "He had a kettle in the garage for eleven years and never once used it." },
      { speaker: "Marlow", text: "And he said it 'had a good face'. That's the part that stayed with me, the face." },
      { speaker: "June", text: "Some objects get a face and you can't throw them out. That's just being human." },
      { speaker: "June", text: "Let's take it slow through the next hour, no rush, nothing to prove." },
      { speaker: "Marlow", text: "If anyone's driving, keep both hands on the wheel, I'll do the talking." },
      { speaker: "June", text: "Here's a record that sounds like a streetlamp on a wet night." },
      { speaker: "Marlow", text: "That's the most accurate description of this song I've heard." },
      { speaker: "June", text: "Take care of the version of you that wakes up tomorrow." },
    ],
  },
  {
    id: "film-club",
    title: "Film Club, Reel Two",
    sampleRateNote: "room mic · 24 kHz",
    lines: [
      { speaker: "Cleo", text: "I want to talk about the eleven minutes where nothing happens." },
      { speaker: "Alun", text: "The eleven minutes are the film though. Take them out and it's just a story." },
      { speaker: "Cleo", text: "Right, but nobody makes eye contact in those eleven minutes." },
      { speaker: "Alun", text: "Because it's two in the morning and they're both pretending to read." },
      { speaker: "Cleo", text: "The lamp does all the acting. It dims and the scene gets sadder without a word." },
      { speaker: "Alun", text: "That's the whole trick of the picture, honestly. Light doing the dialogue." },
      { speaker: "Cleo", text: "It's slow, and I mean that as the highest compliment." },
      { speaker: "Alun", text: "Nothing is wasted. Even the traffic outside is doing something." },
      { speaker: "Cleo", text: "I'd happily watch a version of it that's twice as long and half as loud." },
      { speaker: "Alun", text: "Two hours forty of rain on a window. I'd buy two tickets." },
      { speaker: "Cleo", text: "Let's end on that, before we start arguing about the ending again." },
      { speaker: "Alun", text: "The ending is fine. The ending is quietly perfect." },
    ],
  },
  {
    id: "support",
    title: "Reservation Desk, Evening",
    sampleRateNote: "telephony · 16 kHz",
    lines: [
      { speaker: "Sofia (caller)", text: "Hi, sorry, I know it's late where you are." },
      { speaker: "Toma", text: "Not at all, the desk is open until midnight. How can I help?" },
      { speaker: "Sofia (caller)", text: "I think I booked the wrong Thursday. Twice." },
      { speaker: "Toma", text: "Happens constantly. Let me look at both of them and we'll keep the calmer one." },
      { speaker: "Sofia (caller)", text: "The calmer one is the one by the window, if that's possible." },
      { speaker: "Toma", text: "Window table is free on the second Thursday, quiet side of the room." },
      { speaker: "Sofia (caller)", text: "Perfect. And could we keep it low-key? It's just two of us, no occasion." },
      { speaker: "Toma", text: "No candles, no singing, I'll write that down as a note." },
      { speaker: "Sofia (caller)", text: "You're the first person to take that seriously tonight." },
      { speaker: "Toma", text: "Low-key is a perfectly good way to spend an evening. Confirmed." },
      { speaker: "Sofia (caller)", text: "Thank you. I'll stop refreshing the page now." },
      { speaker: "Toma", text: "You've got a copy in your email, and a table with a view of the rain." },
    ],
  },
  {
    id: "lecture",
    title: "Evening Lecture: Tides",
    sampleRateNote: "lecture hall · 32 kHz",
    lines: [
      { speaker: "Dr. Vasquez", text: "Let's take the whole thing slowly, because tides reward patience." },
      { speaker: "Dr. Vasquez", text: "The moon asks the water for one shape, the coastline answers with another." },
      { speaker: "Pia", text: "So the shape of the bay matters as much as the moon does?" },
      { speaker: "Dr. Vasquez", text: "Enormously. A funnel of a bay can turn a metre of tide into twelve." },
      { speaker: "Pia", text: "And that's why some harbours sit empty twice a day." },
      { speaker: "Dr. Vasquez", text: "Exactly. The water leaves, and the boats have to learn to lean." },
      { speaker: "Pia", text: "I've seen that in the fishing towns, everything tilted at the same angle." },
      { speaker: "Dr. Vasquez", text: "There's a word for it in every coastal language, and they all mean 'waiting'." },
      { speaker: "Dr. Vasquez", text: "The moon is patient. The water is patient. We are the impatient ones." },
      { speaker: "Pia", text: "That's a nicer ending than the maths deserves." },
      { speaker: "Dr. Vasquez", text: "We'll keep the maths. We'll keep the moon. That's the whole course." },
    ],
  },
  {
    id: "poetry",
    title: "Reading Room: Open Mic",
    sampleRateNote: "parlour mic · 24 kHz",
    lines: [
      { speaker: "Host", text: "Next up, reading something new, something short, so be kind." },
      { speaker: "Reader", text: "This one's called 'Kitchen Light', after the fuse in my old flat." },
      { speaker: "Reader", text: "The bulb forgot itself at half past nine, and we waited in the dark like guests." },
      { speaker: "Reader", text: "Rain on a metal roof is the cheapest orchestra, and we had front row seats." },
      { speaker: "Reader", text: "You buttered toast by feel and didn't spill a single crumb." },
      { speaker: "Reader", text: "I learned that laughter needs no wattage, though it does need someone." },
      { speaker: "Reader", text: "We left the light off for the rest of the evening, just to stay in the poem." },
      { speaker: "Host", text: "That's beautiful. Stay for the second half, there's tea at the back." },
      { speaker: "Reader", text: "Thank you. I'll be the one hovering near the kettle." },
      { speaker: "Host", text: "Take your time, take the lamp with you, we've got two more readers." },
    ],
  },
  {
    id: "studio",
    title: "Field Notes, Studio B",
    sampleRateNote: "two lav mics · 48 kHz",
    lines: [
      { speaker: "Ines", text: "When did we start recording these, January? It feels older than that." },
      { speaker: "June", text: "March. You were living on the third floor with the broken radiator." },
      { speaker: "Ines", text: "Right, and I kept calling the microphone a lamp by accident." },
      { speaker: "June", text: "You still do. It's in the transcript, every episode, we can search it." },
      { speaker: "Ines", text: "Let's keep it. It's honest. The lamp is the microphone." },
      { speaker: "June", text: "I like how much of this is just us noticing the room." },
      { speaker: "Ines", text: "That's the show. Two people describing a room very slowly." },
      { speaker: "June", text: "And the room, for the record, is warm, low-lit, and sounds like a cellar." },
      { speaker: "Ines", text: "Keep rolling, then. Nothing to fix, nothing to hurry." },
    ],
  },
];

export const INTERJECTIONS: Line[] = [
  { speaker: "June", text: "Mm." },
  { speaker: "Marlow", text: "Yeah, exactly." },
  { speaker: "Cleo", text: "Right." },
  { speaker: "Alun", text: "Sure, sure." },
  { speaker: "Ines", text: "Hm, that's nice." },
  { speaker: "Toma", text: "Of course." },
];

export interface SeedEntry {
  session: string;
  offset: number;
  speaker: string;
  text: string;
  confidence: number;
  duration: number;
}

/** A little earlier-session history so the panel has depth on first load. */
export const SEED_ENTRIES: SeedEntry[] = [
  { session: "Earlier tonight", offset: 41, speaker: "June", text: "You're on the night shift with me and it's just gone quarter past one.", confidence: 0.97, duration: 4.2 },
  { session: "Earlier tonight", offset: 46, speaker: "Marlow", text: "Which means the calls are about to get honest, that's how it always goes.", confidence: 0.94, duration: 4.6 },
  { session: "Earlier tonight", offset: 53, speaker: "June", text: "Every week. Twelve to two and people start telling me the truth about their kitchens.", confidence: 0.96, duration: 5.1 },
  { session: "Earlier tonight", offset: 61, speaker: "Marlow", text: "I still think about the man who called about the kettle he kept in the garage.", confidence: 0.91, duration: 4.9 },
  { session: "Earlier tonight", offset: 68, speaker: "June", text: "Some objects get a face and you can't throw them out. That's just being human.", confidence: 0.98, duration: 5.4 },
  { session: "This afternoon", offset: 12, speaker: "Sofia (caller)", text: "Hi, sorry, I know it's late where you are.", confidence: 0.93, duration: 3.1 },
  { session: "This afternoon", offset: 16, speaker: "Toma", text: "Not at all, the desk is open until midnight. How can I help?", confidence: 0.95, duration: 4.0 },
  { session: "This afternoon", offset: 22, speaker: "Sofia (caller)", text: "The calmer one is the one by the window, if that's possible.", confidence: 0.9, duration: 3.8 },
  { session: "This afternoon", offset: 28, speaker: "Toma", text: "Low-key is a perfectly good way to spend an evening. Confirmed.", confidence: 0.97, duration: 4.3 },
  { session: "Late morning", offset: 3, speaker: "Reader", text: "Rain on a metal roof is the cheapest orchestra, and we had front row seats.", confidence: 0.92, duration: 5.0 },
  { session: "Late morning", offset: 9, speaker: "Reader", text: "I learned that laughter needs no wattage, though it does need someone.", confidence: 0.89, duration: 4.6 },
  { session: "Late morning", offset: 14, speaker: "Host", text: "Stay for the second half, there's tea at the back.", confidence: 0.96, duration: 3.4 },
];

export const speakerShort = short;
