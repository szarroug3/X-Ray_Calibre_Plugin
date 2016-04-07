package MBP_Reader_Drawing;
# This package generates an image from the drawing data
# stored in DATA...ADQM bytes in an mbp file.
#
# public methods:
# $self = new ([$byte_string, [$drawing_file]])
# $drawing_file = file_name ([$drawing_file])
# $background_color = background_color([$background_color])
# $data = data([$data])
# $log_file = log_file_name ([$log_file])
# $log_file_descriptor = log_file_descriptor ([$log_file_descriptor])
# $log_file_newline = log_file_newline ([$log_file_newline])
# $error = error
# {0|1|2} = generate_MBP_image ([$byte_string, [$drawing_file]])
# $version = version
# $authoring = authoring
#
# private methods:
# _blank
# {0|1} = _write_log ($string)
# _set_error($error)
# _gimme_ADQM_DWORD(['hex'])
#
#
# v0.2.a, 200804, by idleloop@yahoo.com
# http://www.angelfire.com/ego2/idleloop/
#
#
use strict;
use Switch;

# classes used:
use GD;

#constructor
sub new {
	my ($class, $DATA, $file) = @_;
	
	# DATA is always compulsory!
	#if (!defined $DATA) {
	#	return;
	#}

    my $self = {
		# DATA bytes from an mbp DATA...ADQM field.
		DATA	=> undef,
		# DATA bytes from an mbp DATA...ADQM field.
		IMAGE_DATA	=> undef,
		# BACKGROUND color
		BACKGROUND_COLOR => 'ffffff', # white, by default.

		# internal data:
		# ADQM string
		ADQM => undef,

		# image file name (this will hold the generated image)
		FILE_NAME	=> undef, 
		FILE_DESCRIPTOR	=> undef, 

		# Log file name (if any).
		LOG_FILE_NAME	=> undef, # NOT USED.
		# Log file descriptor (if any).
		LOG_FILE_DESCRIPTOR	=> undef, 
		# may be the Carriage Return were previously set with $\, so this could be '':
		LOG_FILE_NEWLINE => "\n",
		# last error description in this object's processes.
		ERROR		=> undef,	
	};
	bless $self, $class;	#'MBP_Reader';

	$self->data($DATA) if (defined $DATA);
	$self->file_name($file) if (defined $file);

    return $self;
}


# returns file name, 
# or sets it. 
sub file_name {
	my ($self, $drawing_file) = @_;
	if (defined $drawing_file) {
		###&_blank(); # erase previous contents in this object.
		$self->{FILE_NAME}=$drawing_file.'.gif';
		return $self->{FILE_NAME};
	} else {
		return $self->{FILE_NAME};
	}
}


# returns log file name, 
# or sets it. 
# If set, it'll be opened for output, overwriting LOG_FILE_DESCRIPTOR.
sub log_file_name {
	my ($self, $log_file) = @_;
	if (defined $log_file) {
		$self->{LOG_FILE_NAME}=$log_file;
		return $self->{LOG_FILE_NAME};
	} else {
		return $self->{LOG_FILE_NAME};
	}
}


# returns log file descriptor, 
# or sets it. 
# If LOG_FILE_NAME is set, it'll be used for output, overwriting LOG_FILE_DESCRIPTOR.
sub log_file_descriptor {
	my ($self, $log_file_descriptor) = @_;
	if (defined $log_file_descriptor) {
		$self->{LOG_FILE_DESCRIPTOR}=$log_file_descriptor;
		return $self->{LOG_FILE_DESCRIPTOR};
	} else {
		return $self->{LOG_FILE_DESCRIPTOR};
	}
}


# returns newline character used when writting to log file, 
# or sets it. 
# (may be the Carriage Return were previously set with $\, so this could be '')
sub log_file_newline {
	my ($self, $log_file_newline) = @_;
	if (defined $log_file_newline) {
		$self->{LOG_FILE_NEWLINE}=$log_file_newline;
		return $self->{LOG_FILE_NEWLINE};
	} else {
		return $self->{LOG_FILE_NEWLINE};
	}
}


# returns background color, 
# or sets it. 
sub background_color {
	my ($self, $background_color) = @_;
	if (defined $background_color) {
		$self->{BACKGROUND_COLOR}=$background_color;
		return $self->{BACKGROUND_COLOR};
	} else {
		return $self->{BACKGROUND_COLOR};
	}
}


# returns DATA string, 
# or sets it. 
sub data {
	my ($self, $data) = @_;
	if (defined $data) {
		$self->{DATA}=$data;
		return $self->{DATA};
	} else {
		return $self->{DATA};
	}
}


# blanks this object
sub _blank {
	my ($self) = @_;
	undef $self->{DATA};
	undef $self->{IMAGE_DATA};
	undef $self->{BACKGROUND_COLOR};
	undef $self->{ADQM};
	undef $self->{FILE_NAME};
	undef $self->{ERROR};
}


# returns last error occurred in this object's processes (if any).
sub error {
	my ($self) = @_;
	if (defined $self->{ERROR}) {
		return $self->{ERROR};
	}
	return '';
}


# writes message to a previously indicated log file name/descriptor.
# if no LOG_FILE_DESCRIPTOR exists, nothing will be written.
sub _write_log {
	my ($self, $string) = @_;
	if (defined $self->{LOG_FILE_DESCRIPTOR}) {
		print {$self->{LOG_FILE_DESCRIPTOR}} $string, 
			$self->{LOG_FILE_NEWLINE};
		return 1;
	}
	return 0;
}


# sets error message string for use of external app, via &error()
sub _set_error {
	my ($self, $error) = @_;
	
	my $file_position=tell($self->{FILE_DESCRIPTOR});
	$error.=' (@ '.$file_position.
			', 0x'.
			# this hexadecimal value will be little-endian-ordered
			# if machine is little endian... be warned! :
			unpack('H*',pack('j',$file_position)).
			')';
	$self->{ERROR}=$error;
}


# reads four bytes from self->ADQM, and
# removes then from self->ADQM string.
# stored readed bytes in self->BUFFER.
sub _gimme_ADQM_DWORD {
	my ($self, $hex) = @_;
	my $buffer='';

	($buffer,$self->{ADQM})=($self->{ADQM}=~/^(....)(.*)$/s);

	if ($hex ne 'hex') {
		$buffer=unpack('N',$buffer); # big endian
	} else {
		$buffer=unpack('H*',$buffer); # big endian
	}

	return $buffer;
}


# Generates image in $drawing_file file, 
# from $DATA (DATA....ADQM) MBP contents.
# Returns 1 on success, 0 on failure, 2 on empty MBP image.
# Errors are left in $self->ERROR, accesible via $self->error
sub generate_MBP_image {
	my ($self, $DATA, $drawing_file) = @_;

	$self->{ERROR}='';

	if (defined $DATA) {
		$self->DATA=$DATA;
	}

	if (defined $drawing_file) {
		$self->file_name($drawing_file);
	}

	# log file:
	if (defined $self->{LOG_FILE_NAME}) {
		# check file name:
		###if (-e $self->{LOG_FILE_NAME}) {
		###	$self->{ERROR}="Log file '$self->{LOG_FILE_NAME}' already exists.";
		###	return 0;
		###}

		# try to open file for appending:
		open (fLog_file, '>>', $self->{LOG_FILE_NAME}) || (
			$self->{ERROR}="Could not open '$self->{LOG_FILE_NAME}' file for writing.",
			return 0
		);
		$self->{LOG_FILE_DESCRIPTOR}=\*fLog_file;
	}

	# check future image file:
	if (-e $self->{FILE_NAME}) {
		$self->{ERROR}="'$self->{FILE_NAME}' already exists. I won't overwrite it.";
		return 0;
	}
	# try to open file for writing:
	open (fDrawing_file, '>', $self->{FILE_NAME}) || (
		$self->{ERROR}="Could not open '$self->{FILE_NAME}' file.",
		return 0
	);
	$self->{FILE_DESCRIPTOR}=\*fDrawing_file;

	# binmode necessary in windows
	binmode(fDrawing_file) || (
		$self->{ERROR}="Could not open '$self->{FILE_NAME}' file in binary mode.",
		return 0
	);

	########################
	# begin process:
	########################
	my ($buffer,
		$XORIG, $YORIG,
		$XMAX, $YMAX,
		$NUM_STROKES,
		$X, $Y,
		$X0, $Y0,
		@strokes,
		$NUM_PAIRS,
		$stroke,
		%pairs, # %pairs stores an array of 2xN elements.
		@pairs,
		$IMAGE,
		$color,
		%palette,
		);

	# Extracts the interesting part of the binary string:
	if ($self->{DATA} !~ /^DATA....ADQM(.+)$/s) {
		$self->{ERROR}="DATA does not conform expected MBP image format (".
			unpack('H*',substr($self->{DATA},0,20)).
			").";
		return 0;
	}
	$self->{ADQM}=$1;

	$self->_write_log( unpack('H*',substr($self->{ADQM},0,20)) .'...' );
	$self->_gimme_ADQM_DWORD;	# I won't use first DWORD
	$XORIG=$self->_gimme_ADQM_DWORD;
	$YORIG=$self->_gimme_ADQM_DWORD;
	$XMAX=$self->_gimme_ADQM_DWORD;
	$YMAX=$self->_gimme_ADQM_DWORD;
	$self->_gimme_ADQM_DWORD; # always 0x 00 00 00 00
	$NUM_STROKES=$self->_gimme_ADQM_DWORD;
	$self->_write_log("0; $XORIG $YORIG $XMAX $YMAX $NUM_STROKES");
	# An empty image still has some data: the BG XMAXxYMAX canvas.
	###if ($NUM_STROKES eq '0') {
	###	return 2; # process correctly finished: no image stored in DATA.
	###}
	foreach (1..$NUM_STROKES) {
		$self->_gimme_ADQM_DWORD; # always 0x 00 00 00 01 ???
		push @strokes, [$self->_gimme_ADQM_DWORD, 
						$self->_gimme_ADQM_DWORD, 
						$self->_gimme_ADQM_DWORD('hex')]; # [begin, end, color]
	}
	$NUM_PAIRS=$self->_gimme_ADQM_DWORD;
	$self->_write_log("1; $XORIG $YORIG $XMAX $YMAX $NUM_STROKES $NUM_PAIRS");
	$stroke=0;
	foreach (0..($NUM_PAIRS-1)) {
		push @pairs, 
			$self->_gimme_ADQM_DWORD - $XORIG, 
			$self->_gimme_ADQM_DWORD - $YORIG;
		$self->_write_log("> $strokes[$stroke][1] - $stroke - $_");
		if ( ($strokes[$stroke][1]-1) == $_ ) {
			$pairs{$stroke}=[@pairs];
			$stroke++;
			@pairs=();
		}
	}

	$self->_write_log(
		"2; $XORIG $YORIG $XMAX $YMAX $NUM_STROKES $NUM_PAIRS $#strokes ".
		(keys %pairs));

	# here begins image construction:
	$IMAGE = new GD::Image($XMAX, $YMAX); # truecolor image
	# background color: first color allocated with colorAllocate:
	$IMAGE->colorAllocate(
		hex(substr($self->{BACKGROUND_COLOR},0,2)),
		hex(substr($self->{BACKGROUND_COLOR},2,2)),
		hex(substr($self->{BACKGROUND_COLOR},4,2))
		);

	# constructs lines, using @strokes and associated %pairs:
	foreach $stroke (0..$#strokes) {
		$color=$strokes[$stroke][2];
		$X=$Y=$X0=$Y0=-1;
		foreach (@{$pairs{$stroke}}) {
			if ($X==-1) {
				$X=$_;
			} else {
				$Y=$_;
			}
			$self->_write_log("$stroke: $_ $X0,$Y0,$X,$Y,$color");
			if ($X0==-1 && $Y!=-1) {
			$self->_write_log('a');
				$X0=$X;
				$Y0=$Y;
				$X=$Y=-1;
			} elsif ($X0!=-1 && $Y!=-1) {
			$self->_write_log('b');
			$self->_write_log("$X0,$Y0,$X,$Y,$color");
				if (!defined $palette{$color}) {
					$palette{$color}=
						$IMAGE->colorAllocate(
							hex(substr($color,2,2)),
							hex(substr($color,4,2)),
							hex(substr($color,6,2)),
						);
				}
				$IMAGE->line($X0,$Y0,$X,$Y,$palette{$color});
				$X0=$X; 
				$Y0=$Y;
				$X=$Y=-1;
			}
		}
	}

	# writes image to file:
	$self->{IMAGE_DATA}=$IMAGE->gif();
	print fDrawing_file $self->{IMAGE_DATA};

	# process end.

	close fLog_file;
	close fDrawing_file;
	undef $self->{FILE_DESCRIPTOR};
	
	return 1;
}


# returns version of MBP_Reader_Drawing.pm
sub version {
	return '0.2.a';
}


# returns MBP_Reader_Drawing.pm authoring string 
sub authoring {
	my ($self)=@_;
	return 
		"MBP file reader\nv".$self->version." (idleloop\@yahoo.com, 200804)\n".
		"http://www.angelfire.com/ego2/idleloop/\n\n";
}


1;