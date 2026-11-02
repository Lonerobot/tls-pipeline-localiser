import pyblish.api
from pyblish.util import publish

from ayon_core.lib.attribute_definitions import FileDefItem
from ayon_core.pipeline import install_host
from ayon_core.pipeline.create import CreateContext
from ayon_traypublisher.api import TrayPublisherHost 
from ayon_core.pipeline import context_tools 
import ayon_api

from pathlib import Path
import json

class PlayblastPublisher():
    def __init__(self, review, variant="Main") -> None:
        self.reviewable = review
        self.representation = review
        self.variant = variant

    def publish_review(self):
        context = context_tools.get_current_context()
        project_name = context["project_name"]
        folder_path = context["folder_path"]
        task_name = context["task_name"]
        variant = self.variant

        create_identifier = "settings_review"

        folder_entity = ayon_api.get_folder_by_path(project_name, folder_path)
        task_entity = ayon_api.get_task_by_name(
            project_name, folder_entity["id"], task_name
        )

        pre_create_data = {
            "representation_files": {self.representation},
            "reviewable": {self.reviewable}
        }

        host = TrayPublisherHost()
        host.set_project_name(project_name)
        install_host(host)

        create_context = CreateContext(host, headless=True)
        create_context.create(
            create_identifier,
            variant,
            folder_entity,
            task_entity,
            pre_create_data
        )

        create_context.save_changes()
        publish_context = pyblish.api.Context()
        publish_context.data["create_context"] = create_context 
        # publish(publish_context, create_context.publish_plugins)

if __name__ == "__main__":    
    test_media = r"D:\renders\publish_tests\buz_flat_review_3d_modeling_Main_v001.mp4"
    pub = PlayblastPublisher(test_media)  
    pub.publish_review()

    