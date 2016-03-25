"""
Django forms for adding PredictDataset objects as well as a Confirmation form

"""
from django import forms
from apps.dropbox_helper.models import DropboxRetrievalLog
from apps.predict.models import PredictDataset
from apps.utils.file_patterns import FILE_TYPE_VCF, FILE_TYPE_FASTQ, FilePatternHelper
from apps.dropbox_helper.dropbox_util import get_dropbox_metadata_from_link
import json

# requires loading of apps/predict/fixtures/initial_data.json
#

class SimpleConfirmationForm(forms.Form):
    confirm = forms.BooleanField(label="Yes, use file(s)", required=False)
    nope = forms.BooleanField(label="No, don't use files.", required=False)

    def do_not_use_files(self):
        assert hasattr(self, "cleaned_data"), "Do not call this unless is_valid() is True"

        return self.cleaned_data.get('nope', False)

    def clean(self):
        is_confirm = self.cleaned_data.get('confirm', False)
        is_nope = self.cleaned_data.get('nope', False)

        if is_confirm is False and is_nope is False:
            msg = "Please confirm whether or not to use these files."
            msg2 = 'Please select ONE of the checkboxes.'
            self.add_error('confirm', msg2)
            self.add_error('nope', msg2)

            raise forms.ValidationError(msg)

        if is_confirm is True and is_nope is True:
            #msg = "Please confirm whether or not to use these files."
            msg2 = 'Please select ONE of the checkboxes.'
            self.add_error('confirm', msg2)
            self.add_error('nope', msg2)

            raise forms.ValidationError(msg2)

        return self.cleaned_data


class UploadPredictionDataForm(forms.ModelForm):
    """
    Form for a user to enter a title, description, and dropbox_url

    The dropbox_url is used to retrieve dropbox metadata
    """
    dropbox_retriever_object = None

    class Meta:
        model = PredictDataset
        fields = ('title', 'file_type', 'fastq_type', 'dropbox_url', 'description', )
        widgets = {
            'dropbox_url': forms.Textarea(attrs={'rows': '4'}),
        }

    def __init__(self, *args, **kwargs):
        super(UploadPredictionDataForm, self).__init__(*args, **kwargs)

        self.fields['dropbox_url'].help_text = 'For help, see \
        <a href="{0}" target="_blank">{0}</a>'.format(self.fields['dropbox_url'].help_text)
        #self.fields['dropbox_url'].widget = forms.TextInput(attrs={'size':'40'}))
        #self.fields['dropbox_url'].widget.attrs.update({'size' : '40'})

    def clean(self):
        file_type = self.cleaned_data.get('file_type', None)
        fastq_type = self.cleaned_data.get('fastq_type')

        # -----------------------------------------
        # If this is a FastQ file, make sure the user
        # has chosen a FastQ type
        # -----------------------------------------
        if file_type == FILE_TYPE_FASTQ and not fastq_type:
            msg = "For FastQ files, please choose a FastQ type"
            self.add_error('fastq_type', msg)
            raise forms.ValidationError(msg)

        # -----------------------------------------
        # Check the dropbox metadata
        # (This should be moved to an async or ajax call in another part of the code )
        # -----------------------------------------
        file_patterns = FilePatternHelper.get_file_patterns_for_dropbox(file_type)

        # Use the dropbox API to look at the files under this dropbox_url
        #
        (success, dbox_retriever_obj_or_err_msg) = get_dropbox_metadata_from_link(\
                                self.cleaned_data.get('dropbox_url'),\
                                file_patterns=file_patterns)
        if success:
            self.dropbox_retriever_object = dbox_retriever_obj_or_err_msg
            #self.dropbox_metadata_info = dbox_retriever_obj_or_err_msg.matching_files_metadata

        else:
            #self.add_error('dropbox_url', dbox_metadata_or_err_msg)
            raise forms.ValidationError(dbox_retriever_obj_or_err_msg)

        return self.cleaned_data

    '''
    def clean_dropbox_url(self):
        """
        This should be an async or ajax call in another part of the code.
        For prototype, we're relying on dropbox uptime, etc.
        """
        #(success, dbox_metadata_or_err_msg) = get_dropbox_metadata_from_link(self.cleaned_data['dropbox_url'])

        #if not success:
        #   raise forms.ValidationError(dbox_metadata_or_err_msg)

        #self.dropbox_metadata_info = dbox_metadata_or_err_msg

        return self.cleaned_data['dropbox_url']
    '''
    def get_dataset(self, tb_user):

        assert hasattr(self, 'cleaned_data'), "Do not call this method on an invalid form. (call is_valid() first)"
        assert tb_user is not None, "tb_user cannot be None"

        # -------------------------------------
        # save PredictDataset, made inactive
        # -------------------------------------
        predict_dataset = self.save(commit=False)   # get object
        predict_dataset.user = tb_user              # set user
        predict_dataset.set_status_not_ready(save_status=False)
        predict_dataset.save()      # save the object

        db_log = DropboxRetrievalLog(dataset=predict_dataset)
        db_log.file_metadata = self.dropbox_retriever_object.dropbox_link_metadata
        db_log.selected_files = self.dropbox_retriever_object.matching_files_metadata
        db_log.save()

        print 'elf.dropbox_retriever_object.dropbox_link_metadata', self.dropbox_retriever_object.dropbox_link_metadata
        print 'self.dropbox_retriever_object.matching_files_metadata', self.dropbox_retriever_object.matching_files_metadata
        #(success, dinfo_or_err_msg) = get_dropbox_metadata(ds)

        return predict_dataset


class DropboxDownloadAttemptForm(forms.Form):

    callback_md5 = forms.CharField()
    success = forms.BooleanField(required=False)
    result_data = forms.CharField(widget=forms.Textarea, required=False)

    def was_run_successful(self):
        assert hasattr(self, 'cleaned_data'), "Must have is_valid() == true.  cleaned_data not found"
        return self.cleaned_data['success']

    def get_run_md5(self):
        assert hasattr(self, 'cleaned_data'), "Must have is_valid() == true.  cleaned_data not found"
        return self.cleaned_data['callback_md5']

    def get_result_data(self):
        assert hasattr(self, 'cleaned_data'), "Must have is_valid() == true.  cleaned_data not found"
        return self.cleaned_data['result_data']


class DatasetRunNotificationForm(forms.Form):

    run_md5 = forms.CharField()
    success = forms.BooleanField(required=False)
    result_data = forms.CharField(widget=forms.Textarea, required=False)

    def was_run_successful(self):
        assert hasattr(self, 'cleaned_data'), "Must have is_valid() == true.  cleaned_data not found"
        return self.cleaned_data['success']

    def get_run_md5(self):
        assert hasattr(self, 'cleaned_data'), "Must have is_valid() == true.  cleaned_data not found"
        return self.cleaned_data['run_md5']

    def get_result_data(self):
        assert hasattr(self, 'cleaned_data'), "Must have is_valid() == true.  cleaned_data not found"
        return self.cleaned_data['result_data']