"""
FastAPI dependency providers.

This is the composition root for Dependency Injection: routes declare what
they need (`Depends(get_db)`, a service, a pagination spec, ...) and this
package is where those providers are assembled, keeping construction logic
out of the route functions themselves.
"""
