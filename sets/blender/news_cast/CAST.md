# Newsroom cast: who, where from, under which licence

Every character is one JSON file next to this one (`<id>.json`) and is cast with `--anchor <id>`. Models live in
`static/avatars/` (house) and `static/avatars/cast/`. Only freely licensed models with redistribution allowed are
accepted. Voices are PUBLIC Fish Audio voices used on the free `s2.1-pro-free` model only (nothing is ever paid for).

| id | on-screen name | model file | source | licence | author / credit | checkFace |
|---|---|---|---|---|---|---|
| `house` | Juno Hale | `static/avatars/default-v1.vrm` | the repo's house VRoid anchor (already in the repo) | repo asset (unchanged) | repo | ok (vroid rig, 17 channels) |
| `vivi` | Vivi Sato | `static/avatars/cast/vivi.vrm` | pixiv VRoid "β Ver AvatarSample_2" (Vivi): https://vroid.pixiv.help/hc/en-us/articles/360014900273 ; file mirrored at https://github.com/madjin/vrm-samples/blob/master/vroid/beta/Vivi.vrm | **CC0 1.0** (pixiv waived all rights; VRM meta `licenseName: CC0`) | pixiv Inc. / VRoid Project | ok (vroid rig after the beta-name fix) |
| `fumiriya` | Fumiriya Sakurada | `static/avatars/cast/fumiriya.vrm` | pixiv VRoid "Sakurada Fumiriya": https://vroid.pixiv.help/hc/en-us/articles/360014788554 ; file https://github.com/madjin/vrm-samples/blob/master/vroid/beta/Sakurada_Fumiriya.vrm | **CC0 1.0** | pixiv Inc. / VRoid Project | ok |
| `theo` | Theo Marsh | `static/avatars/cast/hairsample-male.vrm` | pixiv VRoid "HairSample_Male" (CC0 list: https://vroid.pixiv.help/hc/en-us/articles/4402614652569) ; file https://github.com/madjin/vrm-samples/blob/master/vroid/beta/HairSample_Male.vrm | **CC0 1.0** | pixiv Inc. / VRoid Project | ok |
| `seed` | Seed-san | `static/avatars/cast/seed-san.vrm` | VRM Consortium sample "Seed-san" (vrm-c/vrm-specification samples; mirror https://github.com/madjin/vrm-samples/tree/master/Seed-san) | **VRM Public License 1.0** (https://vrm.dev/licenses/1.0/): modification + redistribution allowed, corporate commercial use allowed, **credit required** | "Seed-san model by VirtualCast, Inc." | ok (new `seed` rig in the expressive map) |

Rejected / not used: VRoid AvatarSample_A/B/C (free to use but NOT CC0, and their terms forbid relicensing),
anything from VRoid Hub behind a login, celebrity or character voice clones on Fish (only generic public voices).

## Voices (public Fish Audio models, free model only)

| id | voice | Fish model id |
|---|---|---|
| house | Hannah (Fish Official; female, professional, clear) | `9a9cf47702da476aa4629e2506d4a857` |
| vivi | Sarah (Fish Official; female, young, soft) | `933563129e564b19a115bedd57b7406a` |
| fumiriya | Ethan (Fish Official; male, calm explainer) | `536d3a5e000945adb7038665781a4aca` |
| theo | Anchor News (public; male, deep, authoritative) | `63d5460e91e2411fa2e6bf95e7456f03` |
| seed | Friendly Women (public; female, bright) | `b545c585f631496c914815291da4e893` |

## Gotchas the import now handles

- VRoid **beta** exports name morphs `Face.M_F00_000_00_Fcl_MTH_A`: `norm_name` strips everything before `Fcl_`
  (Python and TS, golden-tested), else checkFace fails all four core groups.
- They keep morph names per glTF **primitive**: Blender then imports `target_0..`; `hoist_target_names` copies them up.
- **VRM 0.x faces -Z** (VRM 1.0 faces +Z): seated with its back to the lens until turned 180 degrees.
- Alpha-blended eye layers (highlight, the beta `EyeExtra` star layer) must keep their alpha when the unlit material
  is relit, or they paint opaque over the eyes.
- Seed-san's head bone is `head 1`: bones are resolved through the file's VRM humanoid map first.
- Seed-san's backpack robot arm stands up into the close-up: the cast file hides it (`"hide": ["robo_arm"]`).
