from django.db import migrations, models
import django.db.models.deletion


def migrate_sessions(apps, schema_editor):
    SwipeSession = apps.get_model("swipe_sessions", "SwipeSession")
    Session = apps.get_model("common", "Session")

    db = schema_editor.connection.alias

    for swipe_session in SwipeSession.objects.using(db).all():
        Session.objects.using(db).create(
            id=swipe_session.id,
            created_at=swipe_session.created_at,
            updated_at=swipe_session.updated_at,
            session_type="SWIPE_SESSION",
            status=swipe_session.status,
            last_seen_at=swipe_session.last_seen_at,
        )

        for user in swipe_session.users.using(db).all():
            Session.users.through.objects.using(db).create(
                session_id=swipe_session.id,
                user_id=user.id,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0001_add_session"),
        ("swipe_sessions", "0004_remove_generated_at_from_justification"),
    ]

    operations = [
        migrations.RunPython(
            migrate_sessions,
            migrations.RunPython.noop,
        ),

        migrations.RunSQL(
            """
            ALTER TABLE swipe_sessions_swipesession
            RENAME COLUMN id TO session_ptr_id;
            """,
            """
            ALTER TABLE swipe_sessions_swipesession
            RENAME COLUMN session_ptr_id TO id;
            """,
        ),

        migrations.RunSQL(
            """
            ALTER TABLE swipe_sessions_swipesession
            DROP COLUMN created_at;

            ALTER TABLE swipe_sessions_swipesession
            DROP COLUMN updated_at;

            ALTER TABLE swipe_sessions_swipesession
            DROP COLUMN status;

            ALTER TABLE swipe_sessions_swipesession
            DROP COLUMN last_seen_at;
            """,
            migrations.RunSQL.noop,
        ),

        migrations.RunSQL(
            """
            ALTER TABLE swipe_sessions_swipesession
            ADD CONSTRAINT swipe_sessions_swipesession_session_ptr_fk
            FOREIGN KEY (session_ptr_id)
            REFERENCES common_session (id)
            DEFERRABLE INITIALLY DEFERRED;
            """,
            migrations.RunSQL.noop,
        ),

        migrations.RunSQL(
            """
            DROP TABLE swipe_sessions_swipesession_users;
            """,
            migrations.RunSQL.noop,
        ),

        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(
                    name="SwipeSession",
                ),
                migrations.CreateModel(
                    name="SwipeSession",
                    fields=[
                        (
                            "session_ptr",
                            models.OneToOneField(
                                auto_created=True,
                                on_delete=django.db.models.deletion.CASCADE,
                                parent_link=True,
                                primary_key=True,
                                serialize=False,
                                to="common.session",
                            ),
                        ),
                        (
                            "type",
                            models.CharField(
                                choices=[
                                    ("INDIVIDUAL", "Individual"),
                                    ("PAIRED", "Paired"),
                                ],
                                max_length=16,
                            ),
                        ),
                    ],
                    options={
                        "abstract": False,
                    },
                    bases=("common.session",),
                ),
            ],
        ),
    ]