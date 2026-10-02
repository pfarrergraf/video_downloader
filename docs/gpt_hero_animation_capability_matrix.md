# GPT Hero Animation Capability Matrix

## Implemented directly in this branch

| Concept | Status | Implementation |
|---|---|---|
| Perspective smartphone | Implemented | CSS 3D phone with pointer-driven tilt, light treatment and depth |
| Scroll-driven mini film | Implemented | Sticky 260vh section with scroll-linked transformations and progress rail |
| Particle atmosphere | Implemented | Responsive Canvas particle field with pointer repulsion and attraction toward the product |
| Kinetic typography | Implemented | Animated gradient headline with staggered 3D entrance and outlined depth copy |
| Interactive app demo | Implemented | Real buttons and HTML states for share, app selection, format, progress and completion |
| 2.5D depth treatment | Implemented | Separate phone, files, orbit, screen, copy and particle planes |
| Personalised variants | Implemented | Local `?creator=` query parameter and editable creator name |
| Accessibility fallbacks | Implemented | Keyboard-operable controls, semantic labels and `prefers-reduced-motion` mode |

Demo file:

`pro/website/gpt_hero_animation_lab.html`

The production homepage remains unchanged.

## Feasible for GPT, but not honest to call production-ready without dedicated assets or broader browser testing

| Concept | What is still needed |
|---|---|
| Photorealistic WebGL phone | A licensed or custom GLTF model, PBR materials, environment map, texture optimisation and GPU testing |
| Exact particle-to-logo morph | Point sampling from the final logo geometry, worker/offscreen strategy and low-end fallback |
| Liquid image-to-audio shader | Authored GLSL displacement shader, texture sources, art direction and performance profiling |
| Rive state-machine character/icon | A designed `.riv` source file and an animation state specification |
| Cross-page shared-object transition | Final routing decision, browser support policy and fallback testing across the real production flow |
| Automated campaign export at scale | Final language copy, campaign schema, screenshot capture and video render workflow |

## Recommendation

Use the current GPT page as the working baseline and benchmark. Ask Fable 5 to plan the specialist layer only, then compare its plan against this existing implementation before allowing it to alter production files.
