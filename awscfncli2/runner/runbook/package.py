# -*- coding: utf-8 -*-

import logging
import os

import yaml
from awscli.customizations.cloudformation import exceptions
from awscli.customizations.cloudformation.artifact_exporter import Template, \
    Resource, make_abs_path
from botocore.exceptions import ClientError

try:
    from awscli.customizations.cloudformation.artifact_exporter import \
        GLOBAL_EXPORT_DICT
except ImportError:
    # Fix import error before awscli version 1.16.36
    from awscli.customizations.cloudformation.artifact_exporter import \
        EXPORT_DICT as GLOBAL_EXPORT_DICT

from awscli.customizations.s3uploader import S3Uploader

from awscfncli2.config import ConfigError


def package_template(ppt, session, template_path, bucket_region,
                     bucket_name=None, prefix=None, kms_key_id=None):
    # validate template path
    if not os.path.isfile(template_path):
        raise ConfigError('Invalid Template Path "%s"' % template_path)

    # if bucket name is not provided, create a default bucket with name
    # awscfncli-{AWS::AccountId}-                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               {AWS::Region}
    if bucket_name is None:
        sts = session.client('sts')
        account_id = sts.get_caller_identity()["Account"]
        bucket_name = 'awscfncli-%s-%s' % (account_id, bucket_region)
        ppt.secho('Using default artifact bucket {}'.format(bucket_name))
    else:
        ppt.secho('Using artifact bucket {}'.format(bucket_name))

    s3_client = session.client('s3')

    # create bucket if not exists
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            if bucket_region != 'us-east-1':
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={
                        'LocationConstraint': bucket_region
                    }
                )
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name
                )
            ppt.secho('Created artifact bucket {}'.format(bucket_name))
        else:
            raise e

    s3_uploader = S3Uploader(
        s3_client,
        bucket_name,
        bucket_region,
        prefix,
        kms_key_id,
        force_upload=False
    )

    template = Template(template_path, os.getcwd(), s3_uploader,
                        resources_to_export=GLOBAL_EXPORT_DICT)
    exported_template = template.export()
    exported_str = yaml.safe_dump(exported_template)

    ppt.secho('...successfully packaged artifacts and '
              'uploaded file {template_path} to s3://{bucket_name}'.format(
        template_path=template_path, bucket_name=bucket_name))

    return exported_str


# XXX: Hack, Register customized Resource in AWS Cli
class ResourceWithInlineCode(Resource):
    def __init__(self, uploader):
        super(ResourceWithInlineCode, self).__init__(None)

    def export(self, resource_id, resource_dict, parent_dir):
        if resource_dict is None:
            return

        property_value = resource_dict.get(self.PROPERTY_NAME, None)

        if not property_value and not self.PACKAGE_NULL_PROPERTY:
            return

        if isinstance(property_value, dict):
            logging.debug("Property {0} of {1} resource is not a file path"
                          .format(self.PROPERTY_NAME, resource_id))
            return

        try:
            self.do_export(resource_id, resource_dict, parent_dir)

        except Exception as ex:
            logging.debug("Unable to export", exc_info=ex)
            raise exceptions.ExportFailedError(
                resource_id=resource_id,
                property_name=self.PROPERTY_NAME,
                property_value=property_value,
                ex=ex)

    def do_export(self, resource_id, resource_dict, parent_dir):
        """
        Upload to S3 and set property to an dict representing the S3 url
        of the uploaded object
        """

        local_path = resource_dict.get(self.PROPERTY_NAME, None)
        local_path = make_abs_path(parent_dir, local_path)

        with open(local_path, 'r') as fp:
            data = fp.read()

        resource_dict[self.PROPERTY_NAME] = data


class KinesisAnalysisApplicationCode(ResourceWithInlineCode):
    PROPERTY_NAME = 'ApplicationCode'


class StepFunctionsDefinitionString(ResourceWithInlineCode):
    PROPERTY_NAME = 'DefinitionString'


ADDITIONAL_EXPORT = {
    'AWS::KinesisAnalytics::Application': KinesisAnalysisApplicationCode,
    'AWS::StepFunctions::StateMachine': StepFunctionsDefinitionString
}

GLOBAL_EXPORT_DICT.update(ADDITIONAL_EXPORT)