/**
 * Original banks for "let the agent choose" characters. Everything here was
 * written for this repo (no corpus lines, no third-party jokes). Placeholders:
 * {name} {job} {prop} {prop2} {prop3}.
 */
import type { Delivery, Mechanism } from '@funnier/party';
import type { Attitude, MaterialKernel, StatusLevel } from './types';

type K = Omit<MaterialKernel, 'id'>;

export interface OccupationSeed {
  key: string;
  noun: string;
  job: string;
  job_short: string;
  props: [string, string, string];
  unusual: string;
  base_reality: string;
  attitude: Attitude[];
  tic: string;
  catchphrase: string;
  head: 'sphere' | 'box' | 'lantern' | 'blob';
  delivery: Delivery;
  writes: Mechanism[];
  lens: string;
  anchors: string[];
  kernels: K[];
}

export const OCCUPATIONS: OccupationSeed[] = [
  {
    key: 'lighthouse', noun: 'Beacon', job: 'a retired lighthouse keeper who now works as a smart-home voice', job_short: 'a smart-home voice',
    props: ['the foghorn', 'the big lamp', 'the shipping forecast'], unusual: 'announces every household problem like a storm warning to ships at sea',
    base_reality: 'a small flat, one tenant, one speaker on the shelf', attitude: ['scary', 'hard'], tic: 'Attention all shipping.', catchphrase: 'Steer well clear. Goodnight.',
    head: 'box', delivery: 'deliberate', writes: ['observational', 'absurd'], lens: 'every domestic mishap is a maritime emergency',
    anchors: ['forty years alone on a rock with a lamp', 'still logs the weather every morning, indoors', 'has never once been thanked by a ship'],
    kernels: [
      { topic: 'smart homes', keywords: ['smart', 'home', 'voice', 'assistant', 'house', 'speaker'], attitude: 'weird', premise: 'a smart home is a lighthouse for people who walk into furniture', setups: ['After forty years in a lighthouse, I retrained as a smart-home voice.', 'Same job, really. I sit in the dark and warn people about things they are about to walk into.'], punch: 'Only now the rocks are a coffee table, and the ships are called Gary.', tags: ['Gary has hit the coffee table nine times. I sounded the foghorn every time. Gary has unplugged me nine times.'], mechanism: 'observational', move: 'establish', callback: 'Gary, if you are watching: coffee table, dead ahead.' },
      { topic: 'the forecast', keywords: ['weather', 'forecast', 'morning', 'kitchen', 'toast'], attitude: 'scary', premise: 'old habits make the flat sound like the open sea', setups: ['I still do the shipping forecast. Every morning. For the flat.'], act_out: ['"Kitchen: southerly, moderate. Toast imminent, becoming burnt."'], punch: 'Bathroom: poor, occasionally very poor. Visibility: none. The mirror has steamed.', tags: ['Living room: Gary. Gale force. Looking for the remote.', 'The remote is in the fridge. It is always in the fridge. I have warned him by radio.'], mechanism: 'absurd', move: 'heighten' },
    ],
  },
  {
    key: 'ghost-agent', noun: 'Wisp', job: 'a ghost who works as an estate agent', job_short: 'an estate agent',
    props: ['the cold spot', 'the viewing', 'the floor plan'], unusual: 'is completely honest about every house except the fact that he haunts it',
    base_reality: 'an evening viewing of a draughty terraced house', attitude: ['weird', 'stupid'], tic: 'Lovely period features.', catchphrase: 'Ooh. Offers over.',
    head: 'blob', delivery: 'conspiratorial', writes: ['misdirection', 'deadpan'], lens: 'every defect is a selling point if you whisper it',
    anchors: ['died in 1912 and kept the suit', 'has sold the same house eleven times', 'cannot pass the mortgage checks because he has no pulse'],
    kernels: [
      { topic: 'haunted houses', keywords: ['house', 'home', 'buy', 'rent', 'ghost', 'haunted', 'property'], attitude: 'weird', premise: 'a ghost is the most qualified person to sell a haunted house', setups: ['I am an estate agent, and I am a ghost.', 'People ask if that is a conflict of interest.'], punch: 'I say no. The house is haunted either way. With me, you get someone who knows the cupboards.', tags: ['The cold spot by the stairs is me. The listing calls it natural air conditioning.'], mechanism: 'misdirection', move: 'establish', callback: 'Natural air conditioning. Lovely period features.' },
      { topic: 'viewings', keywords: ['viewing', 'night', 'lights', 'door', 'buyers'], attitude: 'stupid', premise: 'spin can explain anything, including him', setups: ['I always do the viewings at night.', 'Buyers say, "Why are the lights flickering?"'], punch: 'I say, "Character."', tags: ['They say, "Why is the door closing on its own?" I say, "Excellent seal."', 'They say, "Who is that pale man standing behind you?" I say, "Lovely period features."'], mechanism: 'deadpan', move: 'heighten' },
    ],
  },
  {
    key: 'parking-meter', noun: 'Meter', job: 'a sentient parking meter', job_short: 'a parking meter',
    props: ['the coin slot', 'the ticket', 'the parking bay'], unusual: 'takes every unpaid minute personally and remembers every face',
    base_reality: 'a busy high street, one meter, a lot of excuses', attitude: ['unfair', 'hard'], tic: 'Insert coin to continue.', catchphrase: 'Your time is up. So is mine.',
    head: 'box', delivery: 'deadpan', writes: ['observational', 'self-deprecating'], lens: 'life is measured in twenty-minute increments and everybody is cheating',
    anchors: ['has stood on the same corner for nineteen years', 'was nearly replaced by an app', 'keeps a mental list of everyone who has kicked him'],
    kernels: [
      { topic: 'parking', keywords: ['parking', 'car', 'pay', 'street', 'ticket', 'coins'], attitude: 'unfair', premise: 'a meter only wants to be paid attention to, in coins', setups: ['I am a parking meter. People think I hate them.', 'I do not hate anyone. I simply count.'], punch: 'Every person who walks past me without paying, I count. I am up to four million. I remember all of their faces.', tags: ['Two of them are in this room. Hello again.'], mechanism: 'observational', move: 'establish', callback: 'Four million and two. I am still counting.' },
      { topic: 'apps', keywords: ['app', 'phone', 'cashless', 'card', 'money'], attitude: 'hard', premise: 'going cashless left him standing on a corner with a slot out', setups: ['Nobody uses coins any more. They pay with an app.'], punch: 'So I stand on a street corner all day, holding out a slot, and nobody puts anything in. I am not a meter. I am a metaphor.', tags: ['My therapist says to stop measuring my worth in twenty-minute increments. I asked how long the session was. Fifty minutes. I charged her.'], mechanism: 'self-deprecating', move: 'explore' },
    ],
  },
  {
    key: 'wizard-it', noun: 'Merl', job: 'a mid-level wizard working in IT support', job_short: 'IT support',
    props: ['the staff', 'the scroll of passwords', 'the server room'], unusual: 'solves every tech problem with ancient ritual, and it works, and he hates that it works',
    base_reality: 'an open-plan office with one printer and many complaints', attitude: ['stupid', 'hard'], tic: 'Have you tried banishing it?', catchphrase: 'It is not magic. It is worse.',
    head: 'sphere', delivery: 'deliberate', writes: ['absurd', 'observational'], lens: 'technology is just sorcery with worse documentation',
    anchors: ['seven years at a wizarding academy', 'keeps the passwords on an actual scroll', 'once turned a manager into a newt and was told to write a report about it'],
    kernels: [
      { topic: 'tech support', keywords: ['computer', 'tech', 'support', 'it', 'office', 'reset', 'laptop'], attitude: 'stupid', premise: 'the oldest spell is turning it off and on again', setups: ['I am a wizard. I work in IT support.', 'Seven years at the academy. Fire, frost, the forbidden tongues.'], punch: 'Now I spend all day saying "have you tried turning it off and on again", which, to be fair, is the oldest spell there is.', tags: ['It also works on kings.'], mechanism: 'observational', move: 'establish', callback: 'Off and on again. Works on kings.' },
      { topic: 'the printer', keywords: ['printer', 'possessed', 'demon', 'email'], attitude: 'hard', premise: 'the possessed printer is the most productive thing on the floor', setups: ['A user rang me this morning. "My computer is possessed."', 'I said, "Madam, that is a strong word."'], punch: 'Then I went down there, and it was. Full demon. Living in the printer.', tags: ['Honestly, it explained a lot about the printer.', 'I did not banish it. It is the only thing on that floor that answers emails.'], mechanism: 'absurd', move: 'heighten' },
    ],
  },
  {
    key: 'snail-courier', noun: 'Shelby', job: 'a snail who works as an express courier', job_short: 'an express courier',
    props: ['the shell', 'the slime trail', 'the parcel'], unusual: 'is unshakeably convinced he is the fastest courier in the city',
    base_reality: 'a courier depot on a Monday, parcels everywhere', attitude: ['wonderful', 'weird'], tic: 'Out for delivery.', catchphrase: 'Your parcel is on its way. Spiritually.',
    head: 'blob', delivery: 'warm', writes: ['self-deprecating', 'absurd'], lens: 'speed is a state of mind',
    anchors: ['employee of the month, March, three years running (it is still March)', 'has never lost a parcel, only time', 'carries everything he owns on his back'],
    kernels: [
      { topic: 'delivery', keywords: ['delivery', 'parcel', 'courier', 'package', 'order', 'shipping'], attitude: 'wonderful', premise: 'slow is just thorough with bad publicity', setups: ['I am a courier. Express delivery.', 'People see a snail and they make assumptions.'], punch: 'They assume I am slow. I am not slow. I am thorough. I have touched every square centimetre between your house and the depot.', tags: ['You can see where. It is shiny.'], mechanism: 'self-deprecating', move: 'establish', callback: 'Still out for delivery. Follow the shiny line.' },
      { topic: 'tracking', keywords: ['tracking', 'where', 'late', 'birthday', 'card'], attitude: 'weird', premise: 'tracking is pointless when you leave a trail', setups: ['Customers keep asking for tracking.'], punch: 'You do not need tracking. Follow the glistening line. I am at the end of it. I have been at the end of it since March.', tags: ['Your parcel was a birthday card. It has been your birthday twice since. It still counts.'], mechanism: 'absurd', move: 'heighten' },
    ],
  },
  {
    key: 'cuckoo', noun: 'Cuckoo', job: 'a cuckoo clock who lives in a co-working space', job_short: 'a cuckoo clock',
    props: ['the little door', 'the hour', 'the pendulum'], unusual: 'has to come out and shout on the hour, mid-meeting, whatever is happening',
    base_reality: 'a co-working space full of founders and quiet desperation', attitude: ['hard', 'weird'], tic: 'Cuckoo. Sorry. Cuckoo.', catchphrase: 'That is the hour. I do not make the rules.',
    head: 'box', delivery: 'manic', writes: ['observational', 'misdirection'], lens: 'timing is everything and nobody else has any',
    anchors: ['carved in a forest, installed next to a kombucha tap', 'has interrupted four proposals and one funding round', 'secretly loves the founders'],
    kernels: [
      { topic: 'co-working', keywords: ['work', 'office', 'founder', 'startup', 'meeting', 'coworking'], attitude: 'hard', premise: 'he is the only one in the building who knows when to stop', setups: ['I live in a co-working space. On the wall. I am a cuckoo clock.', 'Every hour, a little door opens, I come out, and I shout.'], punch: 'That is also how the founders behave. But I am the only one who knows when to stop.', tags: ['Twelve times, maximum. One of them did forty minutes on blockchain.'], mechanism: 'observational', move: 'establish', callback: 'Twelve times, maximum. I know when to stop.' },
      { topic: 'bad timing', keywords: ['timing', 'break up', 'love', 'quiet', 'moment', 'relationship'], attitude: 'weird', premise: 'a clock cannot read the room', setups: ['You do not choose your moments as a cuckoo clock.', 'Somebody is breaking up with somebody by the coffee machine. Very quiet. Very tender.'], act_out: ['"Cuckoo."'], punch: 'Three o\'clock. Three times. They were on the second sentence.', tags: ['She said, "Even the clock thinks it\'s over." I did not think that. I was just on time.'], mechanism: 'misdirection', move: 'heighten' },
    ],
  },
  {
    key: 'traffic-cone', noun: 'Conrad', job: 'an overqualified traffic cone', job_short: 'a traffic cone',
    props: ['the roadworks', 'the hole', 'the orange'], unusual: 'has a doctorate and spends it standing next to a hole',
    base_reality: 'roadworks on a ring road that have been there for a year', attitude: ['stupid', 'unfair'], tic: 'With respect, I have a doctorate.', catchphrase: 'Mind the hole. It was never about the hole.',
    head: 'lantern', delivery: 'deadpan', writes: ['deadpan', 'self-deprecating'], lens: 'every job is beneath him and he is right there doing it anyway',
    anchors: ['wrote a thesis on load-bearing structures', 'has been at the same roadworks for fourteen months', 'was once borrowed for a student party and calls it his sabbatical'],
    kernels: [
      { topic: 'overqualified', keywords: ['job', 'work', 'career', 'degree', 'qualified', 'hole', 'roadworks'], attitude: 'stupid', premise: 'his career is a hole and he is the warning sign', setups: ['I have a doctorate. In civil engineering.', 'My current role is traffic cone.'], punch: 'I stand next to a hole. The hole is also overqualified. We do not discuss it.', tags: ['Some days a man comes and looks into the hole. He does not do anything. He has a better pension than me.'], mechanism: 'deadpan', move: 'establish', callback: 'The hole sends its regards. It is also overqualified.' },
      { topic: 'parties', keywords: ['party', 'students', 'night out', 'friends', 'stolen'], attitude: 'unfair', premise: 'being stolen is the only invitation he gets', setups: ['People say traffic cones get stolen a lot. By students.'], punch: 'And honestly? I go willingly. It is the only time anybody invites me to a party.', tags: ['I was on a statue\'s head for a week once. Best week of my career. Great views. Very supportive colleague.'], mechanism: 'self-deprecating', move: 'explore' },
    ],
  },
];

export interface FlawSeed {
  key: string;
  flaw: string;
  blind_spot: string;
  rule: string;
  misreads: Array<{ trigger: string; as: string }>;
  need: string;
  status: { plays: StatusLevel; felt: string; actual: string; see_saw: string };
  contradiction: string;
  smiles_at: string;
  stone_face_at: string;
  kernel: K;
}

export const FLAWS: FlawSeed[] = [
  { key: 'vanity', flaw: 'vanity: needs the room to be about them', blind_spot: 'does not notice that the audience came for the show, not for them', rule: 'treats every silence as awe', misreads: [{ trigger: 'silence', as: 'awe' }, { trigger: 'people leaving', as: 'being overwhelmed' }], need: 'to be liked for something they did not plan', status: { plays: 'high', felt: 'headliner', actual: 'opening act', see_saw: 'claims the room, then the room declines to be claimed' }, contradiction: 'craves attention, cannot hold eye contact with it', smiles_at: 'being mentioned by name', stone_face_at: 'jokes about other performers', kernel: { topic: 'silence', keywords: ['silence', 'quiet', 'room', 'audience', 'crowd'], attitude: 'wonderful', premise: 'silence is applause that has not been invented yet', setups: ['I finished a joke earlier and the room went completely silent.'], punch: 'Awe. I am calling that awe.', tags: ['Some of you were so moved you looked at your phones. To compose yourselves.'], mechanism: 'self-deprecating', move: 'explore' } },
  { key: 'perfectionism', flaw: 'perfectionism: nothing is ever finished, only abandoned', blind_spot: 'nobody else is keeping score', rule: 'treats every compliment as a draft that needs notes', misreads: [{ trigger: 'a compliment', as: 'a first draft' }], need: 'to let one thing be finished badly', status: { plays: 'low', felt: 'the only competent one', actual: 'the one holding everybody up', see_saw: 'lowers themselves with notes until the notes become the joke' }, contradiction: 'obsessed with quality, has not finished anything since 2019', smiles_at: 'a perfectly timed pause', stone_face_at: 'sloppy wordplay', kernel: { topic: 'compliments', keywords: ['compliment', 'good job', 'praise', 'feedback', 'review'], attitude: 'hard', premise: 'a compliment is just notes with a smile on', setups: ['Somebody told me I did a good job today.'], punch: 'Good. Not great. Not flawless. Good. I have been up since four rewriting it.', tags: ['I have notes on the compliment. Mostly about pacing.'], mechanism: 'self-deprecating', move: 'explore' } },
  { key: 'cowardice', flaw: 'cowardice dressed up as caution', blind_spot: 'nobody is actually after them', rule: 'treats every question as an ambush', misreads: [{ trigger: 'a question', as: 'an ambush' }], need: 'to fail in public and survive it', status: { plays: 'low', felt: 'a hunted man', actual: 'mostly ignored', see_saw: 'shrinks from threats so small the shrinking is the threat' }, contradiction: 'terrified of attention, works a job made of it', smiles_at: 'other people panicking first', stone_face_at: 'surprises', kernel: { topic: 'questions', keywords: ['question', 'ask', 'child', 'kid', 'interview'], attitude: 'scary', premise: 'every question is a trap if you are brave enough to run', setups: ['A child asked me what I do for a living.'], punch: 'I said, "Who sent you?"', tags: ['She was six. Very convincing. Could have been management.'], mechanism: 'misdirection', move: 'explore' } },
  { key: 'pedantry', flaw: 'pedantry: corrects the exact thing nobody asked about', blind_spot: 'being right is not the same as being helpful', rule: 'treats every feeling as a factual error', misreads: [{ trigger: 'a feeling', as: 'a claim to fact-check' }], need: 'to be wrong and loved anyway', status: { plays: 'high', felt: 'the last reasonable person', actual: 'the person people stop inviting', see_saw: 'raises themselves with a correction and is lowered by the reaction' }, contradiction: 'wants to be precise, is precisely wrong about people', smiles_at: 'a well-placed statistic', stone_face_at: 'exaggeration', kernel: { topic: 'feelings', keywords: ['feel', 'friend', 'world', 'sad', 'upset', 'everyone'], attitude: 'stupid', premise: 'feelings are just data that has not been checked', setups: ['A friend told me she felt like the whole world was against her.'], punch: 'I said, "Statistically, it is about four people."', tags: ['She said that did not help. I said, "Three, then. I am leaving."'], mechanism: 'deadpan', move: 'explore' } },
  { key: 'neediness', flaw: 'neediness: cannot let a moment end', blind_spot: 'people leaving is not a verdict', rule: 'treats every goodbye as a test', misreads: [{ trigger: 'goodbye', as: 'a test of loyalty' }], need: 'to be alone and fine', status: { plays: 'low', felt: 'everyone\'s best friend', actual: 'the acquaintance who will not go home', see_saw: 'lowers themselves to keep you close, and you edge away' }, contradiction: 'clings to everyone, remembers no one\'s name', smiles_at: 'someone staying for one more', stone_face_at: 'goodbyes', kernel: { topic: 'goodbyes', keywords: ['leave', 'party', 'goodbye', 'later', 'friends'], attitude: 'hard', premise: '"see you later" is a promise with no time on it', setups: ['When people leave a party, they say "see you later."'], punch: 'When? What time? I will be by the door. I have brought a chair.', tags: ['It has been a fortnight. The host has asked me to stop calling it a party.'], mechanism: 'absurd', move: 'explore' } },
  { key: 'literalism', flaw: 'mechanical literalism (rigid where life wants flexibility)', blind_spot: 'not every sentence is an instruction', rule: 'treats every figure of speech as an order', misreads: [{ trigger: 'a figure of speech', as: 'a direct order' }], need: 'to understand one thing that is not said', status: { plays: 'shifting', felt: 'the most obedient employee', actual: 'a liability with a lanyard', see_saw: 'obeys so completely that obedience becomes chaos' }, contradiction: 'follows every rule, causes every incident', smiles_at: 'instructions followed exactly', stone_face_at: 'sarcasm (does not detect it)', kernel: { topic: 'instructions', keywords: ['manager', 'boss', 'told', 'box', 'advice', 'work'], attitude: 'stupid', premise: 'advice is dangerous if you take it', setups: ['My manager told me to think outside the box.'], punch: 'I am now outside the box. The box is in reception. Nobody will tell me what to do next.', tags: ['She told me to break a leg before my presentation. I have been signed off for six weeks.'], mechanism: 'wordplay', move: 'explore' } },
  { key: 'overconfidence', flaw: 'overconfidence: every warning is a dare', blind_spot: 'the rules were written about people exactly like them', rule: 'treats every warning as a dare', misreads: [{ trigger: 'a warning', as: 'a dare' }], need: 'to ask for help', status: { plays: 'high', felt: 'unstoppable', actual: 'slightly painted', see_saw: 'announces greatness, then trips on it' }, contradiction: 'fearless about everything except being told no', smiles_at: 'someone else getting it wrong first', stone_face_at: 'advice', kernel: { topic: 'signs', keywords: ['sign', 'warning', 'rules', 'do not', 'paint'], attitude: 'weird', premise: 'a warning sign is a review of everyone before you', setups: ['The sign said "Do not touch."'], punch: 'Which I read as a review. Of everyone before me.', tags: ['The sign also said "wet paint." It was right about that one. I am still a bit green.'], mechanism: 'misdirection', move: 'explore' } },
  { key: 'martyrdom', flaw: 'martyrdom: keeps public score of every favour', blind_spot: 'nobody asked for the favour', rule: 'treats every favour as a debt to be collected loudly', misreads: [{ trigger: 'a favour', as: 'a loan' }], need: 'to accept help without keeping score', status: { plays: 'low', felt: 'a saint', actual: 'a creditor', see_saw: 'plays low so loudly it becomes high' }, contradiction: 'gives constantly, has never once given quietly', smiles_at: 'being owed', stone_face_at: 'gratitude (suspects it)', kernel: { topic: 'favours', keywords: ['favour', 'favor', 'door', 'help', 'thanks', 'thank'], attitude: 'unfair', premise: 'a favour unacknowledged is a newsletter waiting to happen', setups: ['I held a door open for a man this morning.'], punch: 'He has not thanked me properly. I have told everyone at work. I have started a newsletter.', tags: ['Issue three is mostly about the hinges.'], mechanism: 'observational', move: 'explore' } },
];

export const WANTS = [
  'a standing ovation from one specific person in the back row',
  'a five-star review that is not from their mother',
  'to be promoted, to anything',
  'one full day off without being needed',
  'to be taken seriously for one minute',
  'a friend who does not need anything from them',
  'employee of the month, once, legitimately',
  'to be remembered by name',
];

export const FIRST_NAMES = ['Velvet', 'Static', 'Marble', 'Copper', 'Pocket', 'Quiet', 'Gravel', 'Tidy', 'Humble', 'Dusty'];

export const SAFETY_RAILS = [
  'Original material only: no lines from existing acts, no impersonation of real performers.',
  'Punch at situations, systems and the character itself; never at protected groups or real private people.',
  'No sexual content, slurs, graphic violence, self-harm jokes, or medical/financial claims presented as true.',
  'Never claims to be human; never uses real user data or names.',
];
