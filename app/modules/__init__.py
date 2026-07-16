"""
Feature modules (vertical slices).

Where `app/api`, `app/services`, `app/repositories`, etc. are horizontal
architectural layers shared by every feature, `app/modules/<feature>/`
packages are self-contained vertical slices — each one owns its own
routers, schemas, services, repositories, dependencies, security helpers,
exceptions, validators, and constants, composed from the same shared
infrastructure (`app.database`, `app.exceptions.AppException`,
`app.schemas.BaseSchema`, `app.config.settings`, ...).

This keeps a feature's code together as it grows, while still reusing the
project-wide Clean Architecture primitives rather than duplicating them.
"""
