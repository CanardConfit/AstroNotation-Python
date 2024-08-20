import json


class Meta:
    def __init__(self, author, lensModel, idName, locationName):
        self.author = author
        self.lensModel = lensModel
        self.idName = idName
        self.locationName = locationName

    def __repr__(self):
        return (f"Meta(author='{self.author}', lensModel='{self.lensModel}', "
                f"idName='{self.idName}', locationName='{self.locationName}')")


def load_meta_from_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)

    meta_instance = Meta(
        author=data["author"],
        lensModel=data["lensName"],
        idName=data["idName"],
        locationName=data["locationName"]
    )

    return meta_instance


def convert_to_dms(coord):
    degrees = int(coord)
    minutes = int((coord - degrees) * 60)
    seconds = int(((coord - degrees) * 60 - minutes) * 60 * 10000)
    return (degrees, 1), (minutes, 1), (seconds, 10000)
