import pyblish.api
from pyblish.util import publish

# from openpype.client import get_asset_by_name
# from openpype.lib.attribute_definitions import FileDefItem
# from openpype.pipeline import install_host
# from openpype.pipeline.create import CreateContext
# from openpype.hosts.traypublisher.api import TrayPublisherHost

# from openpype.pipeline import context_tools

##################
# AYON REFACTOR 
##################
from ayon_core.lib.attribute_definitions import FileDefItem
from ayon_core.pipeline import install_host
from ayon_core.pipeline.create import CreateContext
from ayon_traypublisher.api import TrayPublisherHost 
from ayon_core.pipeline import context_tools 
import ayon_api

from pathlib import Path
import json

class PlayblastPublisher():
    def __init__(self, root_folder) -> None:
        self.root_folder = Path(root_folder)

        """
        There seems to be some nuances about executing this class 
        as a supbrocess. 

        I tried numerous ways to have global constants for the 
        publishing naming conventions, but having the process 
        aware of the relative imports needed was troublesome

        So I am reverting to having a JSON settings file and 
        loading it where needed.         
        """
        settings_file = Path(__file__).parent.absolute() / 'settings.json'
        with open(settings_file) as f:
            settings = json.load(f)

        self.reviewable = settings["review_prefix"]
        self.representation = settings["representation_prefix"]
        self.variant = settings["variant"]

    def globData(self,pattern, ext):
        file_names = []
        for f in self.root_folder.glob(f'{pattern}*{ext}'):
            file_names.append(str(f))
        return file_names

    def get_reviewable(self, ext='.mp4'):
        return self.globData(self.reviewable, ext)

    def get_representation(self, ext='.png'):
        return self.globData(self.representation, ext)

    def publish_review(self):
        context = context_tools.get_current_context()
        project_name = context["project_name"]
        folder_path = context["folder_path"]
        task_name = context["task_name"]
        variant = self.variant
        sequence_paths = self.get_representation()
        review_paths = self.get_reviewable()
        # Based on which create plugin should be used
        create_identifier = "settings_review"

        folder_entity = ayon_api.get_folder_by_path(project_name, folder_path)
        task_entity = ayon_api.get_task_by_name(
            project_name, folder_entity["id"], task_name
        )

        representation_files = FileDefItem.from_value(sequence_paths, True)
        if len(representation_files) != 1:
            raise ValueError(
                "Couldn't figure out single representation item from paths."
            )

        reviewable = FileDefItem.from_value(review_paths, True)
        if len(reviewable) > 1:
            raise ValueError(
                "Couldn't figure out single reviewable item from paths."
            )

        representation_item = representation_files[0].to_dict()
        reviewable_item = reviewable[0].to_dict()

        pre_create_data = {
            "representation_files": representation_item,
            "reviewable": reviewable_item
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
        publish(publish_context, create_context.publish_plugins)

if __name__ == "__main__":
    
    import sys
    args = sys.argv[1:] 
        
    if args and args[0]:
        print(f'Publishing review media from {args[0]}')
        pub = PlayblastPublisher(args[0])  
        pub.publish_review()

    