.. _html-templating:

HTML Templating
===============

pygeoapi uses `Jinja`_ as its templating engine to render HTML and `Flask`_ to provide route paths of the API that returns HTTP responses. For complete details on how to use these modules, refer to the `Jinja documentation`_ and the `Flask documentation`_.

The default pygeoapi configuration has ``server.templates`` commented out and defaults to the pygeoapi ``pygeoapi/templates`` and ``pygeoapi/static`` folder. To point to a different set of template configuration, you can edit your configuration:

.. code-block:: yaml

  server:
    templates:
      path: /path/to/jinja2/templates/folder # jinja2 template HTML files
      static: /path/to/static/folder # css, js, images and other static files referenced by the template

**Note:** the URL path to your static folder will always be ``/static`` in your deployed web instance of pygeoapi.

Your templates folder should mimic the same file names and structure of the default pygeoapi templates. Otherwise, you will need to modify ``api.py`` accordingly.

Note that you need only copy and edit the templates you are interested in updating.  For example,
if you are only interested in updating the ``landing_page.html`` template, then create your own version
of the only that same file.  When pygeoapi detects that a custom HTML template is being used,
it will look for the custom template in ``server.templates.path``.  If it does not exists, pygeoapi
will render the default HTML template for the given endpoint/requuest.

Linking to a static file in your HTML templates can be done using Jinja syntax and the exposed ``config['server']['url']``:

.. code-block:: html

  <!-- CSS example -->
  <link rel="stylesheet" href="{{ config['server']['url'] }}/static/css/default.css">
  <!-- JS example -->
  <script src="{{ config['server']['url'] }}/static/js/main.js"></script>
  <!-- Image example with metadata -->
  <img src="{{ config['server']['url'] }}/static/img/logo.png" title="{{ config['metadata']['identification']['title'] }}" />


.. _`Jinja`: https://palletsprojects.com/p/jinja/
.. _`Jinja documentation`: https://jinja.palletsprojects.com
.. _`Flask`: https://palletsprojects.com/p/flask/
.. _`Flask documentation`: https://flask.palletsprojects.com
