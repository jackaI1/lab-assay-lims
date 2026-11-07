# Component source

I generated the button, badge, label, and separator files in `components/ui/` with the official shadcn CLI, using its base-nova style, then adjusted the surrounding theme and sizing for this queue. `components.json` keeps that registry configuration. The components use Base UI primitives where needed. Native HTML dropdowns handle the fixed visit and priority choices.

The copied component source is covered by [shadcn/ui's MIT license](shadcn-license.txt). To add another component later, I can run `npx shadcn@latest add <component>`. The CLI itself is not shipped with the app.
