"""
Copyright 2013 Rackspace

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import falcon
import json

from jsonschema.exceptions import ValidationError


class ApiResource(object):

    def format_response_body(self, body_dict):
        return json.dumps(body_dict)

    def abort(self, status=falcon.HTTP_500, message=None):
        """
        Helper function for aborting an API request process. Useful for error
        reporting and exception handling.
        """
        raise falcon.HTTPError(status, message)

    def load_body(self, req, validator=None):
        """
        Helper function for loading an HTTP request body from JSON into a
        Python dictionary
        """
        try:
            raw_json = req.stream.read()
        except Exception:
            self.abort(falcon.HTTP_500, 'Read Error')

        try:
            obj = json.loads(raw_json)
        except ValueError:
            self.abort(falcon.HTTP_400, 'Malformed JSON')

        if validator:
            try:
                validator.validate(obj)
            except ValidationError as e:
                err_msg = self._format_validation_error_message(e)
                self.abort(falcon.HTTP_400, err_msg)

        return obj

    def _format_validation_error_message(self, error):
        err_msg = "JSON validation failed"
        if error.path:
            err_msg += ": invalid value for key {0}".format(list(error.path))
        err_msg += " - {0}".format(error.message)
        return err_msg

    def on_get(self, req, resp):
        resp.status = falcon.HTTP_404

    def on_post(self, req, resp):
        resp.status = falcon.HTTP_404

    def on_delete(self, req, resp):
        resp.status = falcon.HTTP_404
