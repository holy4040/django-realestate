from rest_framework.exceptions import APIException

class PropertyNotFound(APIException):
    status_code = 404
    default_detail = "The request property doesn't exist"