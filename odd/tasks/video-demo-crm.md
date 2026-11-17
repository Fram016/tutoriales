# Video demo: crear un contacto en Nexo CRM

Trial run of the whole skill set by a delegated agent, so the user can watch how it works and give feedback on the skills.
App: demo-apps/nexo-crm/index.html served at http://127.0.0.1:8766/ (in-memory data, every load starts clean).

## Specs

- S1 "generes un video demo, quiero ver como trabajas de ahi te dare observaciones para que vayamos mejorand skills" — produce a finished tutorial and a work log of how the skills were followed, with friction found.
- S2 "delega subagente para que haga video" — a subagent produces the video following the project skills.
- S3 "puede ser como crear un registro en un CRM haz un video prueb" — topic: create a record (contact) in a CRM.
- S4 "primero levanta un HTML, delegas con la sinstrucciones de uso" — a local HTML CRM is served first; the subagent gets usage instructions like a user would give.

## Tasks

- [x] T1 S3,S4 — Build and serve demo-apps/nexo-crm (login, sidebar, contacts list, new-contact form with validation) — parent
- [ ] T2 S1,S2,S3 — Subagent produces proyectos/nexo-crm-contacto: brief → guion → ensayo → captura → voz → edición → render → QA, plus work log — worker

## Log

- L1 (user): "Ahora necesiot uqe generes un video demo, quiero ver como trabajas de ahi te dare observaciones para que vayamos mejorand skills, delega subagente para que haga video, puede ser como crear un registro en un CRM haz un video prueb. para ello primero levanta un HTML, delegas con la sinstrucciones de uso"
- L2 (parent): demo credentials stored in proyectos/nexo-crm-contacto/acceso.local.yaml as NEXO_CRM_CONTACTO_USER / NEXO_CRM_CONTACTO_PASSWORD (values never passed to the subagent).
- L3 (usage instructions given to the subagent, as a user would): "Nexo CRM es un CRM de ventas. Se ingresa con correo y contraseña. En el menú lateral está Contactos; ahí se ve la lista y el botón '+ Nuevo contacto'. El formulario pide Nombre, Apellido y Correo como obligatorios; también Empresa, Cargo, Teléfono, Etapa (Prospecto, Negociación, Cliente), Origen y Notas. Al guardar vuelve a la lista, el contacto aparece primero y resaltado, y sale un aviso verde. Hay un buscador arriba de la lista. Enfoque: vendedores nuevos que cargan su primer prospecto; tono cercano; 16:9 de 60-90 s y 9:16 de menos de 45 s."
