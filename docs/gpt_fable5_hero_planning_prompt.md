# Planning Prompt for Claude Fable 5

You are acting as a senior creative technologist, interactive art director, WebGL engineer, motion designer, accessibility specialist and performance engineer.

Repository:

`pfarrergraf/video_downloader`

Product:

`DownloadThat`

## Mode and hard boundary

Work in **planning and audit mode only**.

Do not implement, install packages, modify production files, commit generated code or open a pull request during this task. You may inspect the repository and write planning documents on a dedicated planning branch only if the environment requires a file output.

Proposed planning branch:

`fable/hero-animation-plan`

The purpose of this task is to produce an expert implementation plan for advanced web-animation effects that go beyond the existing GPT baseline.

## Existing GPT baseline

First inspect:

- `pro/website/gpt_hero_animation_lab.html`
- `docs/gpt_hero_animation_capability_matrix.md`
- `pro/website/index.html`
- `CLAUDE.md`
- `pro/README.md`
- `pro/website/i18n.js`
- existing assets under `pro/website/assets/`
- real application screenshots under `store_assets/`
- current homepage and download flow

The GPT laboratory page already contains:

- CSS 3D smartphone presentation
- pointer-responsive tilt
- Canvas particle atmosphere
- kinetic typography
- scroll-linked product storytelling
- a keyboard-operable interactive product demo
- 2.5D layering
- reduced-motion fallback
- query-parameter creator personalisation

Do not propose rebuilding those same features with different names unless your approach produces a clearly measurable improvement.

## Planning target

Plan the specialist effects that cannot honestly be considered production-ready without dedicated assets, WebGL art direction or browser/performance validation:

1. photorealistic WebGL smartphone with real product UI;
2. precise particle-to-DownloadThat-logo morph;
3. liquid or refractive shader transitions between video, audio, image and saved-file states;
4. a premium reactive DownloadThat arrow built as a Rive state machine or an equally maintainable vector-animation system;
5. robust shared-object transitions from Hero to download or pricing flow;
6. scalable campaign variants for languages, creators and affiliate links;
7. a production integration strategy combining the best specialist effects with the current lightweight GPT baseline.

## Product and legal truth

Do not invent:

- supported platforms;
- discounts;
- user numbers;
- testimonials;
- guaranteed compatibility;
- guaranteed earnings;
- DRM circumvention;
- App Store or Play Store availability.

Preserve the core legal message:

`Only save content for which the user has the required rights or permission.`

Inspect the repository for current price, licensing, privacy and affiliate facts before using them in a storyboard.

## Required audit

Document the current state before proposing a design:

- current page architecture;
- deployment model;
- build constraints;
- existing colour and typography system;
- existing screenshots and their resolutions;
- missing assets;
- current i18n mechanism;
- current mobile behaviour;
- current performance risks;
- current accessibility strengths and weaknesses;
- browser support requirements;
- whether the production site can remain no-build;
- whether specialist rendering must be isolated from the main page.

Create:

`docs/FABLE5_HERO_CURRENT_STATE_AUDIT.md`

## Three concept directions

Develop three genuinely different art-direction concepts.

### Direction A — Product Cinema

Focus:

- photorealistic 3D smartphone;
- high-quality material, reflections and lighting;
- real app UI mapped onto the display;
- controlled camera movement;
- premium technology-advertising tone;
- subtle depth of field without harming readability.

### Direction B — Data Becomes Local

Focus:

- links and media fragments as particles;
- exact morph into the DownloadThat symbol;
- video, audio and image states represented through motion;
- a clear visual metaphor for data moving into the user’s own device;
- strong final CTA state.

### Direction C — Fluid Format Transformation

Focus:

- shader-driven transformation from video frame to waveform to image grid to saved file;
- premium liquid, refractive or chromatic transition;
- interaction with scroll or pointer movement;
- a lightweight fallback that keeps the same story.

For each direction provide:

- one-sentence concept;
- target audience;
- first eight seconds storyboard in 0.5-second increments;
- desktop composition;
- mobile composition;
- interaction model;
- technical stack;
- required assets;
- performance risks;
- accessibility fallback;
- implementation complexity;
- maintenance cost;
- likely conversion benefit;
- reasons it could fail;
- what differentiates it from the GPT baseline.

Create:

`docs/FABLE5_HERO_CONCEPT_DIRECTIONS.md`

## Scored recommendation

Score each concept from 1 to 10 using a weighted model:

- immediate comprehension: 20%;
- visual distinction: 15%;
- product truth: 15%;
- mobile performance: 15%;
- desktop performance: 10%;
- accessibility: 10%;
- maintainability: 10%;
- localisation suitability: 5%.

Show the calculation, not only the final score.

Select:

- one primary direction;
- one reduced mobile direction;
- one fallback direction for reduced motion and weak GPUs.

Do not select a concept only because it is technically impressive.

## Photorealistic 3D phone planning

Plan the full production pipeline without implementing it.

Address:

- source of the phone model: custom, licensed or procedural;
- GLTF/GLB structure;
- polygon budget;
- texture resolution;
- PBR materials;
- screen texture replacement;
- environment maps;
- reflections;
- lighting rig;
- camera path;
- device orientation;
- Three.js or alternative runtime;
- tree shaking and code splitting;
- lazy loading;
- GPU capability detection;
- mobile downgrade strategy;
- screenshot/video texture refresh process;
- asset licensing record;
- loading placeholder;
- failure state.

Define exact budgets:

- compressed GLB size;
- texture size;
- JavaScript size;
- first meaningful frame;
- target frame rate by device class;
- maximum GPU memory estimate.

## Exact particle morph planning

Plan a deterministic particle system that can morph between:

1. scattered media symbols;
2. a smartphone silhouette;
3. the DownloadThat arrow/logo;
4. a completed local file.

Specify:

- how geometry or SVG paths are sampled;
- point count by device class;
- CPU versus GPU simulation;
- vertex and fragment responsibilities;
- use of instancing, transform feedback, GPGPU or simpler alternatives;
- deterministic seeds;
- pointer interaction;
- worker or OffscreenCanvas strategy;
- resizing behaviour;
- fallback for low-memory devices;
- reduced-motion static state;
- how the logo remains recognisable;
- performance validation method.

## Shader transition planning

Plan one shader effect that supports the product story rather than functioning as decoration.

Compare at least:

- displacement/noise dissolve;
- liquid refraction;
- RGB/chromatic separation;
- signed-distance-field morph;
- texture atlas transition.

Select one and provide:

- visual logic;
- required input textures;
- uniform list;
- interaction variables;
- timing curve;
- colour-space handling;
- WebGL 1/WebGL 2 strategy;
- fallback implementation;
- seizure/flashing safeguards;
- target GPU cost;
- profiling plan.

## Reactive arrow or Rive system

Plan a premium animated DownloadThat arrow with states:

- idle;
- attention;
- hover;
- pressed;
- receiving a link;
- downloading;
- success;
- error;
- reduced motion.

Decide whether Rive is justified.

If Rive is selected, define:

- artboard structure;
- state machine inputs;
- event names;
- data-binding fields;
- file-size target;
- web runtime integration;
- fallback SVG/CSS version;
- ownership of the editable `.riv` source.

If Rive is not selected, explain the maintainable alternative.

## Shared-object transition planning

Plan transitions from the Hero CTA or device into:

- `/download`;
- `#pricing`;
- the licence checkout introduction.

Address:

- View Transition API support;
- same-document versus cross-document transitions;
- history navigation;
- keyboard activation;
- deep links;
- no-JavaScript fallback;
- Stripe and withdrawal-modal boundaries;
- avoiding misleading continuity between marketing UI and payment UI.

Do not modify checkout, Stripe URLs, withdrawal logic or affiliate attribution as part of the animation project.

## Localisation and campaign variants

Plan how one animation system supports:

- German;
- English;
- French;
- Spanish;
- Italian;
- Arabic with RTL;
- Japanese;
- Chinese;
- creator name;
- creator code;
- affiliate link;
- campaign identifier;
- desktop, mobile and social-video exports.

Address:

- text expansion;
- line breaking;
- CJK fonts;
- Arabic shaping and direction;
- dynamic textures in WebGL;
- DOM text versus baked textures;
- SEO and accessibility;
- screenshot and video export automation;
- deterministic campaign configuration.

## Performance architecture

Propose three tiers:

### Tier 0 — Static/reduced motion

- image or lightweight DOM composition;
- no continuous animation;
- full product comprehension;
- keyboard and screen-reader support.

### Tier 1 — Standard interactive

- current GPT baseline or equivalent;
- CSS transforms and limited Canvas;
- target for most phones and laptops.

### Tier 2 — Cinematic GPU

- WebGL phone, particle morph or shader;
- loaded only after capability and network checks;
- never blocks primary content or CTA.

Define the capability-routing rules using signals such as:

- `prefers-reduced-motion`;
- viewport size;
- device memory where available;
- hardware concurrency;
- connection quality where available;
- WebGL renderer capability;
- measured frame time after warm-up.

Do not use user-agent sniffing as the main strategy.

## Performance budgets

Propose explicit pass/fail values for:

- LCP;
- CLS;
- INP;
- total blocking time in lab tests;
- JavaScript transferred;
- GLB transferred;
- textures transferred;
- average and 95th-percentile frame time;
- memory use;
- battery/thermal degradation test;
- mobile data usage.

Include a rule that the CTA and headline must remain available before the cinematic tier finishes loading.

## Accessibility and safety

Plan for:

- `prefers-reduced-motion`;
- keyboard-only operation;
- visible focus;
- screen-reader order;
- meaningful static alternative;
- no important information conveyed only by motion;
- no rapid flashing;
- contrast compliance;
- paused animation when the page is hidden;
- user replay and pause controls;
- mobile touch targets;
- text zoom up to 200%;
- forced-colours behaviour.

## Browser and device test matrix

Include at minimum:

- current Chrome desktop;
- current Edge desktop;
- current Firefox desktop;
- current Safari desktop;
- Android Chrome on low, medium and high device classes;
- Samsung Internet;
- iOS Safari even if Android is the product focus;
- landscape and portrait;
- 360, 390, 768, 1024, 1440 and 1920 pixel widths;
- reduced motion;
- slow 4G;
- no JavaScript;
- WebGL unavailable;
- WebGL context loss.

## Asset production list

Create a precise asset request table containing:

- asset name;
- purpose;
- source owner;
- format;
- pixel dimensions or polygon budget;
- alpha requirements;
- colour space;
- licensing requirement;
- whether it already exists;
- exact capture or creation instructions.

Include real DownloadThat screen captures for:

- share entry point;
- Android share sheet;
- DownloadThat selection;
- format choice;
- queue/progress;
- completed download;
- free/licence state where appropriate.

Never fabricate a UI screenshot and present it as a real product screen.

## Implementation phases

Design a phased plan:

### Phase 0 — Measurement baseline

Measure current production Hero and GPT lab.

### Phase 1 — Asset-ready vertical slice

One device, one language, one eight-second sequence.

### Phase 2 — Specialist effect

Only the selected advanced effect.

### Phase 3 — Adaptive tiers

Tier 0, Tier 1 and Tier 2 routing.

### Phase 4 — Localisation

Eight languages and RTL/CJK validation.

### Phase 5 — Production integration

Feature flag, analytics, A/B test and rollback.

For each phase specify:

- inputs;
- outputs;
- files likely to change;
- tests;
- acceptance criteria;
- rollback point;
- reasons not to proceed.

## Benchmark against GPT

Use the GPT laboratory page as a fixed baseline.

Create a benchmark table comparing:

- first visual impact;
- product comprehension after five seconds;
- interaction quality;
- uniqueness;
- mobile smoothness;
- transferred bytes;
- accessibility;
- localisation effort;
- maintenance complexity;
- failure behaviour.

Do not claim Fable is better merely because its solution uses WebGL or more code.

Define a blind-review protocol:

- same product copy;
- same assets;
- same viewport;
- same device;
- same network profile;
- anonymised Variant A/Variant B;
- at least five task-based reviewers;
- comprehension question;
- CTA-location task;
- preference question;
- motion-comfort question.

## Analytics and success criteria

Plan events for:

- Hero viewed;
- cinematic tier loaded;
- animation replayed;
- interaction started;
- each product-demo state reached;
- CTA clicked;
- fallback used;
- WebGL failure;
- reduced-motion mode.

Do not collect sensitive personal information.

Define success as a combination of:

- comprehension;
- CTA engagement;
- performance;
- accessibility;
- error rate;
- user preference.

## Required final documents

Produce:

1. `docs/FABLE5_HERO_CURRENT_STATE_AUDIT.md`
2. `docs/FABLE5_HERO_CONCEPT_DIRECTIONS.md`
3. `docs/FABLE5_HERO_TECHNICAL_ARCHITECTURE.md`
4. `docs/FABLE5_HERO_ASSET_REQUESTS.md`
5. `docs/FABLE5_HERO_PERFORMANCE_AND_ACCESSIBILITY.md`
6. `docs/FABLE5_HERO_IMPLEMENTATION_PHASES.md`
7. `docs/FABLE5_VS_GPT_HERO_BENCHMARK_PLAN.md`
8. `docs/FABLE5_HERO_FINAL_RECOMMENDATION.md`

## Final response format

Report:

- what you inspected;
- what already exists in the GPT baseline;
- the three concept directions;
- the scored winner;
- the selected mobile and reduced-motion variants;
- required assets;
- proposed technology choices;
- performance budgets;
- implementation phases;
- benchmark method;
- unresolved decisions;
- explicit statement that no production implementation was performed.

Do not start implementation. Stop after the complete planning package is ready.
