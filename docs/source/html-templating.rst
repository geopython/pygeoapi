.. _html-templating:

HTML Templating
===============

pygeoapi uses `Jinja`_ as its templating engine to render HTML and `Flask`_ to provide route paths of the API that returns HTTP responses. For complete details on how to use these modules, refer to the `Jinja documentation`_ and the `Flask documentation`_.

The default pygeoapi configuration has ``server.template`` commented out and defaults to the pygeoapi ``pygeoapi/templates`` and ``pygeoapi/static`` folder. To point to a different set of template configuration, you can edit your configuration:

.. code-block:: yaml

  server:
    template:
      path: /path/to/jinja2/templates/folder # jinja2 template HTML files
      static: /path/to/static/folder # css, js, images and other static files referenced by the template

**Note:** the URL path to your static folder will always be ``/static`` in your deployed web instance of pygeoapi.

Your templates folder should mimic the same file names and structure of the default pygeoapi templates. Otherwise, you will need to modify ``api.py`` accordingly.

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