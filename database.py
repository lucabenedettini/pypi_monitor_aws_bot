import django
from django.conf import settings
from django.db import models, connections


class Database:
    # https://gist.github.com/mw3i/b879895272a28d1c789f23ee91555620
    def __init__(self, engine='django.db.backends.sqlite3', name=None, user=None, password=None, host=None, port=None):
        self.Model = None

        # Define the DATABASES dictionary
        databases = {
            'default': {
                'ENGINE': engine,
                'NAME': name,
                'USER': user,
                'PASSWORD': password,
                'HOST': host,
                'PORT': port,
                'APP_LABEL': 'isolated',
            }
        }

        # Update the settings with the custom DATABASES dictionary
        settings.configure(
            DATABASES=databases,
            INSTALLED_APPS=[
                'user_package',
            ]
        )

        # Initialize Django
        django.setup()

        # Create the custom base model
        class CustomBaseModel(models.Model):
            class Meta:
                app_label = 'isolated'
                abstract = True

        self.Model = CustomBaseModel

    # Create a table if it doesnt exist
    def create_table(self, model):
        with connections['default'].schema_editor() as schema_editor:
            if model._meta.db_table not in connections['default'].introspection.table_names():
                schema_editor.create_model(model)

    # Update table if you added fields (doesn't drop fields as far as i know, which i was too afraid to implement)
    def update_table(self, model):
        with connections['default'].schema_editor() as schema_editor:
            # Check if the table exists
            if model._meta.db_table in connections['default'].introspection.table_names():
                # Get the current columns in the table
                current_columns = [field.column for field in model._meta.fields]

                # Get the database columns
                database_columns = connections['default'].introspection.get_table_description(
                    connections['default'].cursor(), model._meta.db_table)
                database_column_names = [column.name for column in database_columns]

                # Check if each field in the model exists in the database table
                for field in model._meta.fields:
                    if field.column not in database_column_names:
                        # Add the new column to the table
                        schema_editor.add_field(model, field)
