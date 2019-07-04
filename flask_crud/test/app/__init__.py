from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_crud import ResourceView, CRUD, CollectionView
from flask_rest_api import Api, Blueprint
from marshmallow import fields as f, Schema
from sqlalchemy import inspect
import os

db = SQLAlchemy()

from flask_crud.test.app.model import Pet, Human

api = Api()

debug = bool(os.getenv("DEBUG"))


def create_app() -> Flask:
    app = Flask("CRUDTest")
    app.config.update(
        OPENAPI_VERSION="3.0.2",
        SQLALCHEMY_DATABASE_URI=f"sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ECHO=debug,
    )
    db.init_app(app)
    api.init_app(app)
    CRUD(app)

    app.register_blueprint(pet_blp)
    app.register_blueprint(human_blp)
    app.register_blueprint(pointless_blp)

    return app


class HumanSchema(Schema):
    id = f.Integer(dump_only=True)  # not editable
    name = f.String()
    pets = f.Nested("PetSchemaLite", exclude=("human",))


class PetSchemaLite(Schema):
    id = f.Integer(dump_only=True)  # not editable
    genus = f.String()
    species = f.String()
    human = f.Nested(HumanSchema, exclude=("pets",))


class PetSchema(PetSchemaLite):
    edible = f.Boolean()


pet_blp = Blueprint("pets", "pets", url_prefix="/pet")


@pet_blp.route("")
class PetCollection(CollectionView):
    model = Pet
    prefetch = [Pet.human, (Pet.human, Human.cars)]  # joinedload

    create_enabled = True
    list_enabled = True

    _decorators = dict(
        post=[
            pet_blp.arguments(PetSchema),
            pet_blp.response(PetSchema),
        ],
    )

    @pet_blp.response(PetSchemaLite(many=True))
    def get(self):
        query = super().get()

        # check prefetch worked
        first = query.first()
        assert is_rel_loaded(first, "human"), "failed to prefetch rel 'human'"
        assert is_rel_loaded(first.human, "cars"), "failed to prefetch secondary relationship 'human' -> 'car'"

        return query


@pet_blp.route("/<int:pk>")
class PetResource(ResourceView):
    model = Pet

    get_enabled = True  # enabled by default
    update_enabled = True
    delete_enabled = True

    # get_decorators = [pet_blp.response(PetSchema)]
    _decorators = dict(
        get=[pet_blp.response(PetSchema)],
        patch=[
            pet_blp.arguments(PetSchema),
            pet_blp.response(PetSchema),
        ],
        delete=[pet_blp.response(PetSchema)],
    )


human_blp = Blueprint("humans", "humans", url_prefix="/human")


@human_blp.route("")
class HumanCollection(CollectionView):
    model = Human


@human_blp.route("/<int:pk>")
class HumanResource(ResourceView):
    model = Human

    _decorators = dict(
        get=[human_blp.response(HumanSchema)],
    )


pointless_blp = Blueprint(
    "pointless", "pointless", url_prefix="/pointless", description="No methods allowed"
)


@pointless_blp.route("/<int:pk>")
class PointlessResource(ResourceView):
    model = Human
    get_enabled = False


def is_rel_loaded(item, attr_name):
    """Test if a relationship was prefetched."""
    ins = inspect(item)
    # not unloaded aka loaded aka chill
    return attr_name not in ins.unloaded
