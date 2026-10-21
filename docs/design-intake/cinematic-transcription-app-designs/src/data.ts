export interface TranscriptLine {
  speaker?: string;
  text: string;
}

export interface Session {
  id: string;
  title: string;
  tag: string;
  date: string;
  duration: string;
  /** seconds after midnight when the session started, for timestamps */
  startSec: number;
  lines: TranscriptLine[];
}

export interface CommittedLine {
  speaker?: string;
  text: string;
  t: string;
}

export const wordCount = (s: Session) =>
  s.lines.reduce((n, l) => n + l.text.split(/\s+/).length, 0);

export const fmtClock = (sec: number) => {
  const s = ((sec % 86400) + 86400) % 86400;
  let h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ap = h >= 12 ? "PM" : "AM";
  h = h % 12 || 12;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")} ${ap}`;
};

export const fmtElapsed = (sec: number) => {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
};

export const SESSIONS: Session[] = [
  {
    id: "night-drive",
    title: "Night Drive FM — Ep. 42",
    tag: "late radio",
    date: "Tonight",
    duration: "58:12",
    startSec: 2 * 3600 + 41 * 60 + 7,
    lines: [
      {
        speaker: "Mara",
        text: "Welcome back to the late shift. It's just past two, and the city is finally breathing slow.",
      },
      {
        speaker: "Jonas",
        text: "You can hear it, right? The hum of the streetlights, the rain deciding whether to stay.",
      },
      {
        speaker: "Mara",
        text: "Tonight we're talking about the quiet hours — why they feel longer, and softer.",
      },
      {
        speaker: "Jonas",
        text: "I think it's because nobody's asking anything of you at two a.m. The night just lets you be.",
      },
      {
        speaker: "Mara",
        text: "There's a kind of honesty in an empty street. Like the whole world pressed pause for you.",
      },
      {
        speaker: "Jonas",
        text: "And the radio becomes a small window with the light on. Someone else is awake too.",
      },
      {
        speaker: "Mara",
        text: "So wherever you're driving, or lying awake — this next one's for you. Stay with us a while.",
      },
      { speaker: "Jonas", text: "Windows down, volume low. The good kind of alone." },
    ],
  },
  {
    id: "rain-skylight",
    title: "Rain on the Skylight",
    tag: "field notes",
    date: "Tue · 1:15 AM",
    duration: "40:03",
    startSec: 1 * 3600 + 15 * 60 + 22,
    lines: [
      {
        text: "Note to self — the rain started around eleven, tapping the skylight like it wanted in.",
      },
      {
        text: "Recorded forty minutes of it over the studio. No music, just water finding its rhythm.",
      },
      {
        text: "Somewhere in the middle, a train went past. You can hear it if you listen low.",
      },
      {
        text: "I like thinking someone else is hearing the same rain from another roof.",
      },
      { text: "Keep the take. Fade it under the intro of episode nine." },
    ],
  },
  {
    id: "slow-hours",
    title: "The Slow Hours — Sleep & Dreams, Pt. 2",
    tag: "podcast",
    date: "Mon · 11:48 PM",
    duration: "1:12:40",
    startSec: 23 * 3600 + 48 * 60 + 40,
    lines: [
      {
        speaker: "Ada",
        text: "Most people don't fall asleep all at once. They arrive in layers.",
      },
      {
        speaker: "Ada",
        text: "First the body gets heavy, then the thoughts start losing their edges.",
      },
      {
        speaker: "Ben",
        text: "Like a conversation in the next room you stop trying to follow.",
      },
      {
        speaker: "Ada",
        text: "Exactly. And dreams are what happens when you finally stop knocking.",
      },
      {
        speaker: "Ben",
        text: "So the trick isn't to chase sleep. It's to stop guarding the door.",
      },
      {
        speaker: "Ada",
        text: "You'd be surprised how much of insomnia is just politeness — refusing to let go.",
      },
    ],
  },
  {
    id: "diner-fifth",
    title: "Diner on Fifth, 3:07 A.M.",
    tag: "memo",
    date: "Sun · 3:07 AM",
    duration: "12:56",
    startSec: 3 * 3600 + 7 * 60 + 11,
    lines: [
      {
        text: "Two coffees at the counter, steam curling like it has nowhere to be.",
      },
      {
        text: "The cook hums something old. The jukebox is off, but you can feel it waiting.",
      },
      {
        text: "She says the night shift is the honest shift. Nobody performs at three in the morning.",
      },
      { text: "I write that down on a napkin. It smudges before I'm done." },
      { text: "Outside, a taxi idles in the rain like it's thinking it over." },
    ],
  },
  {
    id: "study-take4",
    title: "Voice Memo — Study Session, Take 4",
    tag: "voice memo",
    date: "Sat · 12:26 AM",
    duration: "03:41",
    startSec: 0 * 3600 + 26 * 60 + 5,
    lines: [
      { text: "Okay, last pass before bed. Keep this one short." },
      {
        text: "The mix needs more air around the piano. Pull the reverb back a touch.",
      },
      {
        text: "Vocals sit better when they're a little tired, a little unguarded.",
      },
      {
        text: "Render the quiet version. The loud one can wait for morning people.",
      },
      { text: "And maybe leave the tape hiss in. It sounds like company." },
    ],
  },
  {
    id: "coastal-walk",
    title: "Coastal Walk, Past Midnight",
    tag: "walk",
    date: "Fri · 12:52 AM",
    duration: "26:18",
    startSec: 0 * 3600 + 52 * 60 + 33,
    lines: [
      {
        text: "The waves sound different at night. Rounder, like they're speaking slower.",
      },
      {
        text: "No one on the path but me and a dog that clearly knows the way.",
      },
      {
        text: "Moonlight does this thing on the water — breaks it into moving coins.",
      },
      { text: "I could stand here until the tide forgets me. Almost did." },
      {
        text: "Heading back. The lighthouse blinked twice, which I'm choosing to take personally.",
      },
    ],
  },
];
