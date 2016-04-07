package MBP_User_Mark_DATA;
# This package models a DATA block associated to one particular 
# "user mark" in a .MBP file.
# which are the files that store user added information to
# any of the file formats that "mobipocket reader" can read.
# So, a .MBP file associated to a (for example) .PRC book file,
# would contain annotations, corrections, drawings and marks
# made by the user on the .PRC content.
#
# public methods:
# new ([$DATA])
# index_pointer ([$index_pointer])
# DATA ($DATA)
# $text = text_get
#
# private methods:
# _data_text ($DATA)
#
#
# v0.3.a, 201203, by idleloop@yahoo.com
# http://www.angelfire.com/ego2/idleloop/
#
#
use strict;
# 201203 UTF-16BE:
use Encode;
use Encode::Unicode; # (needed just for win32 packaging)

#constructor
sub new {
	my ($class) = shift;
    my $self = {
		# all DATA block bytes, in raw.
		DATA		=> shift,	
		# DATA block index table pointer
        DATA_index	=> undef,	
		# DATA block position in MBP file
		DATA_position			=> undef,	
		# DATA block index table position in MBP file's 
		DATA_index_posititon	=> undef,	
		# index data associated to this DATA block, in MBP file's index table 
		DATA_index_data			=> undef,	
		# ASCII text (if this DATA block contains stores text)
		DATA_text	=> undef,	
	};
    bless $self, $class;	#'MBP_User_Mark_DATA';
    return $self;
}


# returns index of this objet in index table,
# or sets it.
sub index_pointer {
	my ($self, $index_pointer) = @_;
	if (defined $index_pointer) {
		$self->{DATA_index}=$index_pointer;
	} else {
		return $self->{DATA_index};
	}
}


# returns the DATA block associated to this DATA object,
# or sets it.
sub DATA {
	my ($self, $DATA) = @_;
	if (defined $DATA) {
		$self->{DATA}=$DATA;
		$self->_data_text($DATA);
	} else {
		return $self->{DATA};
	}
}


# sets the text associated to this DATA object, 
# if it's appropriate.
sub _data_text {
	my ($self, $DATA) = @_;
	if (defined $DATA) {
		if (
			($DATA=~/^DATA/ && $DATA!~/^DATA....(?:EBVS|EBAR|ADQM)/) ||
			($DATA=~/^DATA\x00\x00\x00\x00/) || # 20090622: DATA can be empty, though this line do not pose a real difference
			($DATA=~/^(?:CATE|AUTH|TITL|GENR|ABST|COVE|PUBL)/) #::type_list::
			) {
			my $text_length=unpack('N',substr($DATA,4,4));
			my $text;
			if ($text_length<=(length($DATA)-8)) {
				$text=substr($DATA,8,$text_length);
				#$text=~s/\x00//g; # # 201203 UTF-16BE: it's UTF-16BE !!!
				# 201203 UTF-16BE: gonna convert this to more readable UTF-8:
				$text=decode("UTF-16BE", $text);
				$self->{DATA_text}=$text;
			}
		}
	}
}


# returns the text associated to this DATA object, 
# if any.
sub text_get {
	my ($self) = @_;
	if (defined $self->{DATA_text}) {
		return $self->{DATA_text};
	}
}



1;