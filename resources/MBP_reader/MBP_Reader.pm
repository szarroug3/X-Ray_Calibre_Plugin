package MBP_Reader;
# This package reads a .MBP file,
# which is the sort of files that store user added information to
# any of the file formats that "mobipocket reader" can read.
# So, a .MBP file associated to a (for example) .PRC book file,
# would contain annotations, corrections, drawings and marks
# made by the user on the .PRC content.
# After reading and parsing the book, this package stores:
# file path+name:				FILE_NAME
# complete file in a scalar:	FILE		
# header block:					HEADER		
# BPARMOBI block:				BPARMOBI	
# Number of next free pointer in index table:	BPARMOBI_NEXT_FREE_POINTER
# Number of entries in index table:				BPARMOBI_NUMBER_INDEX_ENTRIES
# index_table block:			INDEX_TABLE	
# BPAR Mark block:				BPAR_MARK
# DATA User Marks block in an array:	USER_MARKS_DATA
# BKMK User Marks block in an array:	USER_MARKS_BKMK
#
# public methods:
# $self = new ($mbp_file)
# $mbp_file = file_name ([$mbp_file])
# $log_file = log_file_name ([$log_file])
# $file = file
# $header = header
# $bparmobi = bparmobi
# $index_table = index_table
# $user_marks = user_marks
# $user_marks_data = user_marks_data
# $user_marks_bkmk = user_marks_bkmk
# $error = error
# {0|1} = process ([$mbp_file])
# $version = version
# $authoring = authoring
#
# private methods:
# _blank
# $buffer = _read_mbp_file ($file_descriptor, $number_of_bytes)
# {0|1} = _write_log ($string)
# _set_error($error)
#
#
# v0.5.c, 201311, by idleloop@yahoo.com
# http://www.angelfire.com/ego2/idleloop/
#
#
use strict;

# classes used:
use lib '.';
use MBP_User_Mark;
use MBP_User_Mark_DATA;
use MBP_User_Mark_BKMK;


#constructor
sub new {
	my ($class, $mbp_file) = @_;
	
	# mbp_file is always compulsory!
	if (!defined $mbp_file) {
		return;
	}

    my $self = {
		# file path+name.
		FILE_NAME	=> $mbp_file,
		# file descriptor
		FILE_DESCRIPTOR	=> undef, 

		# complete file contents in a scalar.
		FILE		=> undef,	
		# header block.
		HEADER		=> undef,	
		# BPARMOBI block.
        BPARMOBI	=> undef,	
		# integer
		BPARMOBI_NEXT_FREE_POINTER		=> undef,	
		# integer
		BPARMOBI_NUMBER_INDEX_ENTRIES	=> undef,	
		# index_table block.
		INDEX_TABLE	=> undef,	
		# BPAR Mark block
		BPAR_MARK	=> undef,
		# DATA User Marks block in an array.
		USER_MARKS_DATA	=> undef,	
		# BKMK User Marks block in an array.
		USER_MARKS_BKMK	=> undef,	

		# Refewrence to an Array of MBP User Mark objects (MBP_User_Mark).
		MBP_USER_MARKS	=> undef,	

		# Log file name (if any).
		LOG_FILE_NAME	=> undef,	
		# Log file descriptor (if any), from LOG_FILE_NAME.
		LOG_FILE_DESCRIPTOR	=> undef, 
		# last error description in this object's processes.
		ERROR		=> undef,	
	};
	bless $self, $class;	#'MBP_Reader';

    return $self;
}


# returns file name, 
# or sets it. 
# If it's set, all the previous results are erased.
sub file_name {
	my ($self, $mbp_file) = @_;
	if (defined $mbp_file) {
		&_blank(); # erase previous contents in this object.
		$self->{FILE_NAME}=$mbp_file;
		return $self->{FILE_NAME};
	} else {
		return $self->{FILE_NAME};
	}
}


# returns log file name, 
# or sets it. 
sub log_file_name {
	my ($self, $log_file) = @_;
	if (defined $log_file) {
		$self->{LOG_FILE_NAME}=$log_file;
		return $self->{LOG_FILE_NAME};
	} else {
		return $self->{LOG_FILE_NAME};
	}
}


# blanks this object
sub _blank {
	my ($self) = @_;
	undef $self->{FILE_NAME};
	undef $self->{FILE};
	undef $self->{HEADER};
	undef $self->{BPARMOBI};
	undef $self->{INDEX_TABLE};
	undef $self->{USER_MARKS_DATA};
	undef $self->{USER_MARKS_BKMK};
	undef $self->{ERROR};
}


# returns FILE scalar, if &process was previously called.
sub file {
	my ($self) = @_;
	if (defined $self->{FILE}) {
		return $self->{FILE};
	}
}


# returns HEADER scalar, if &process was previously called.
sub header {
	my ($self) = @_;
	if (defined $self->{HEADER}) {
		return $self->{HEADER};
	}
}


# returns BPARMOBI scalar, if &process was previously called.
sub bparmobi {
	my ($self) = @_;
	if (defined $self->{BPARMOBI}) {
		return $self->{BPARMOBI};
	}
}


# returns INDEX_TABLE scalar, if &process was previously called.
sub index_table {
	my ($self) = @_;
	if (defined $self->{INDEX_TABLE}) {
		return $self->{INDEX_TABLE};
	}
}


# returns USER_MARKS* scalar, if &process was previously called.
sub user_marks {
	my ($self) = @_;
	if (defined $self->{USER_MARKS_DATA} && 
		defined $self->{USER_MARKS_BKMK}) {
		return $self->{USER_MARKS_DATA} .
			$self->{USER_MARKS_BKMK};
	}
}


# returns USER_MARKS_DATA scalar, if &process was previously called.
sub user_marks_data {
	my ($self) = @_;
	if (defined $self->{USER_MARKS_DATA}) {
		return $self->{USER_MARKS_DATA};
	}
}


# returns USER_MARKS_BKMK scalar, if &process was previously called.
sub user_marks_bkmk {
	my ($self) = @_;
	if (defined $self->{USER_MARKS_BKMK}) {
		return $self->{USER_MARKS_BKMK};
	}
}


# returns last error occurred in this object's processes (if any).
sub error {
	my ($self) = @_;
	if (defined $self->{ERROR}) {
		return $self->{ERROR};
	}
	return '';
}


# writes message to previously indicated log file.
# ...this functionality hasn't been expanded...
sub _write_log {
	my ($self, $string) = @_;
	if (defined $self->{LOG_FILE_DESCRIPTOR}) {
		print {$self->{LOG_FILE_DESCRIPTOR}} $string, "\n";
		return 1;
	}
	return 0;
}


# reads from file the number of bytes indicated:
sub _read_mbp_file {
	my ($self, $file_descriptor,$number_of_bytes) = @_;
	my ($buffer);

	if (!defined read($file_descriptor,$buffer,$number_of_bytes)) {
		# treat error
		$self->{ERROR}='Problem while reading file.';
		;
	}

	$self->{FILE}.=$buffer; # store file contents in FILE.
	
	return $buffer;	
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


# Reads MBP $mbp_file file, and process and parsers all it contents.
# Returns 1 on success, 0 on failure.
# Errors are left in $self->ERROR, accesible via $self->error
sub process {
	my ($self, $mbp_file) = @_;

	$self->{ERROR}='';

	if (defined $mbp_file) {
		$self->file_name($mbp_file); # automatically calls _blank
	} else {
		$self->file_name($self->{FILE_NAME}); # automatically calls _blank
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

	# check file name:
	if (!-r $self->{FILE_NAME}) {
		$self->{ERROR}="'$self->{FILE_NAME}' is not a readable file.";
		return 0;
	}

	# try to open file:
	open (fMBP_file, '<', $self->{FILE_NAME}) || (
		$self->{ERROR}="Could not open '$self->{FILE_NAME}' file.",
		return 0
	);
	$self->{FILE_DESCRIPTOR}=\*fMBP_file;

	# binmode necessary in windows
	binmode(fMBP_file) || (
		$self->{ERROR}="Could not open '$self->{FILE_NAME}' file in binary mode.",
		return 0
	);

	my ($buffer,$state_marker,$intermediate_state_marker,

		# variables to manage the index table:
		$index_table_counter,%index_table,$index_table_pointer,@index_table,
		$BKMK_type, @BKMK_pointers,
		# we need a DATA hash in which to store references (by identifier)
		# to all the DATA blocks (objetcs) that we don't know to which 
		# object they belong:
		%DATA,
		# and a temporal scalar buffer to store data as it's processed:
		$DATA_BUFFER,
		# counts BKMK objects (= real order of the mark in the book):
		$index_table_bkmk_marker,
		# stores BKMK color, if the BKMK type uses it (DRAWING, for exmaple):
		$BKMK_color,
		);

	# finite state machine transitions descriptor:
	my %STATE=( 
		0	=> 1, # HEADER
		1	=> 2, # BPARMOBI
		2	=> 3, # BPARMOBI_NEXT_FREE_POINTER
		3	=> 4, # BPARMOBI_NUMBER_INDEX_ENTRIES   
		4	=> 5, # INDEX_TABLE
		5	=> 6, # BPAR
		6	=> 7, # DATA
		7	=> 10, # BKMK
		10	=> -1,# END OF FILE (state never reached in FSM block)
	);

	$state_marker=0; # we begin trying to read HEADER contents.
	# used to follow: AUTH, TITL, CATE, GENR, ABST, COVE, PUBL #::type_list::
	$intermediate_state_marker=''; 

	while (!eof(fMBP_file)) {

		# 20090622: patch: 
		#	alinement can be out of a 4 byte boundary, but in a 2 byte boundary (!?)
		if ($state_marker == 6 && # DATA
					# we're not and the end of markers arrya... (?)
				$#index_table != $index_table_counter && 
					# not in a 4 byte alinement !
				($index_table[$index_table_counter+1] - 
						$index_table[$index_table_counter])%4 != 0 && 
					# just for the first time
				tell(fMBP_file) == ($index_table[$index_table_counter] + 4) 
		) {
			# 20090622: patch: 
			# 2 bytes just for this time in order to recover the 4 byte alinement.
			# read 2 bytes from $mbp_file and stores them in $self->{FILE}
			$buffer = $self->_read_mbp_file(\*fMBP_file, 2);
		} else {
			# read 4 bytes from $mbp_file and stores them in $self->{FILE}
			$buffer = $self->_read_mbp_file(\*fMBP_file, 4);
		}

		#########################################
		{ ###swicth ($state_marker) { # finite state machine (FSM)

		  #--------------------------------------
		  # HEADER state
		  if ($state_marker==0)
		  {
			if ($buffer eq 'BPAR' && tell(fMBP_file)>56) {
				$self->{BPARMOBI}.=$buffer;
				$state_marker=$STATE{$state_marker};
			} else {
				$self->{HEADER}.=$buffer;
			}
		  }

		  #--------------------------------------
		  # BPARMOBI state
		  elsif ($state_marker==1)
		  {
			$self->{BPARMOBI}.=$buffer;
			if ($buffer eq 'MOBI') {
				$state_marker=$STATE{$state_marker};
			} else {
				$self->_set_error(
					'Finite Machine error while waiting for BPARMOBI tag'
				);
			}
		  }

		  #--------------------------------------
		  # BPARMOBI_NEXT_FREE_POINTER state
		  elsif ($state_marker==2)
		  {
			$self->{BPARMOBI}.=$buffer;
			$self->{BPARMOBI_NEXT_FREE_POINTER}=unpack('N',$buffer); # big endian
			# there's a strange 2 byte pad here, so:
			# read 2 bytes from $mbp_file
			$buffer = $self->_read_mbp_file(\*fMBP_file, 2);
			$self->{BPARMOBI}.=$buffer;
			$state_marker=$STATE{$state_marker};
		  }

		  #--------------------------------------
		  # BPARMOBI_NUMBER_INDEX_ENTRIES state
		  elsif ($state_marker==3)
		  {
			$self->{BPARMOBI}.=$buffer;
			$self->{BPARMOBI_NUMBER_INDEX_ENTRIES}=unpack('N',$buffer); # big endian
			$index_table_counter=0;
			@index_table=();
			%index_table=();
			$state_marker=$STATE{$state_marker};
		  }

		  #--------------------------------------
		  # INDEX_TABLE state
		  elsif ($state_marker==4)
		  {
			$self->{INDEX_TABLE}.=$buffer;

			# we're now in the index table... all this info must be added to 
			# MBP User Mark objects, but we can't group it without BKMK infos,
			# so we're gonna store it temporally in %index_table 
			# and @index_table.

			# In even indexes are the pointers to file positions.
			if ($index_table_counter % 2 == 0) {
				$index_table_pointer=unpack('N',$buffer); # big endian
			} else {
				# In odd indexes are the pointer identifiers.
				$index_table{ $index_table_pointer }
					= unpack('N',$buffer);	# big endian
				push @index_table, $index_table_pointer;
			}

			$index_table_counter++;

			# test if all index entries have been read 
			# (and then, change to next state):
			if (($index_table_counter/2)==$self->{BPARMOBI_NUMBER_INDEX_ENTRIES}) {
				# there's a strange 2 byte pad here, so:
				# read 2 bytes from $mbp_file
				$buffer = $self->_read_mbp_file(\*fMBP_file, 2);
				$self->{INDEX_TABLE}.=$buffer;
				$index_table_counter=0;
				$state_marker=$STATE{$state_marker};
			}
		  }

		  #--------------------------------------
		  # BPAR state
		  elsif ($state_marker==5)
		  {
			if (tell(fMBP_file)==($index_table[$index_table_counter]+4) 
				&& $buffer ne 'BPAR') {
				$self->_set_error(
					'Error: expecting BPAR block in User Marks Area, '.
					' but '.unpack('H*',$buffer).' found'); # hexadecimal representation
				return 0;
			}
			
			$self->{BPAR_MARK}.=$buffer;
			$self->{USER_MARKS_DATA}.=$buffer;

			if (tell(fMBP_file)==($index_table[$index_table_counter+1])) {

				# store this BPAR data in a User Mark object:
				my $MBP_local=new MBP_User_Mark;
				$MBP_local->type('BPAR');
				# this is the only case in which we know the order now:
				$MBP_local->order($index_table_counter);
				# associate a DATA object to it:
				my $MBP_data_local=new MBP_User_Mark_DATA;
				$MBP_data_local->DATA($self->{BPAR_MARK});
				$MBP_data_local->index_pointer($index_table_counter);
				$MBP_local->DATA_insert($MBP_data_local);
				# and we can store it now... 
				# (next DATA objects will need to wait to BKMK blocks analysis).
				push @{$self->{MBP_USER_MARKS}}, $MBP_local;
				
				# jump to next register
				$index_table_counter++;
				$state_marker=$STATE{$state_marker};
			}
		  }

		  #--------------------------------------
		  # DATA state
		  elsif ($state_marker==6)
		  {
			$DATA_BUFFER.=$buffer;
			$self->{USER_MARKS_DATA}.=$buffer;

			if (tell(fMBP_file)==($index_table[$index_table_counter]+4) 
				# 20090622: there can be empty DATA's inserted in between... so no use to next line:
				### && $buffer ne 'DATA') { 
				) { 

				if ($buffer eq 'BKMK') {
					# we have ended DATA blocks, so we must pass to next state:
					# (and also jump to next index table register)
					###$index_table_counter++; # DO NOT inc now! we're already correct!
					###$DATA_BUFFER=''; # don't erase: we'll continue reading this BKMK.
					# previous word read, weren't a DATA block, but a BKMK block:
					$self->{USER_MARKS_DATA}=substr($self->{USER_MARKS_DATA},0,-4);
					$self->{USER_MARKS_BKMK}=$buffer;
					# sets BKMK object count:
					$index_table_bkmk_marker=0;
					# and set next state:
					$state_marker=$STATE{$state_marker};
					# switch now to next state (another iteration=> another read):
					last; 
				} 

				#::type_list::

				  elsif ($buffer eq 'AUTH') {
					# we have ended all DATA blocks, and this is a AUTH text block
					$intermediate_state_marker='AUTHOR';
					# and continue... later, $intermediate_state_marker 'll be checked. 
				} elsif ($buffer eq 'TITL') {
					# we have ended all DATA blocks, and this is a TITL text block
					$intermediate_state_marker='TITLE';
					# and continue... later, $intermediate_state_marker 'll be checked. 
				} elsif ($buffer eq 'CATE') {
					# we have ended all DATA blocks, and this is a CATE text block
					$intermediate_state_marker='CATEGORY';
					# and continue... later, $intermediate_state_marker 'll be checked. 
				} elsif ($buffer eq 'GENR') {
					# we have ended all DATA blocks, and this is a GENR text block
					$intermediate_state_marker='GENRE';
					# and continue... later, $intermediate_state_marker 'll be checked. 
				} elsif ($buffer eq 'ABST') {
					# we have ended all DATA blocks, and this is a ABST text block
					$intermediate_state_marker='ABSTRACT';
					# and continue... later, $intermediate_state_marker 'll be checked. 
				} elsif ($buffer eq 'COVE') {
					# we have ended all DATA blocks, and this is a COVE text block
					$intermediate_state_marker='COVER';
					# and continue... later, $intermediate_state_marker 'll be checked. 
				} elsif ($buffer eq 'PUBL') {
					# we have ended all DATA blocks, and this is a COVE text block
					$intermediate_state_marker='PUBLISHER';
					# and continue... later, $intermediate_state_marker 'll be checked. 
				} elsif ($buffer eq 'DATA') {
					# we have reach a strange empty DATA block (DATA\x00\x00\x00\x00)
					$intermediate_state_marker='EMPTY_DATA';
					# and continue... later, $intermediate_state_marker 'll be checked. 
				} else {
					if ($buffer=~/^[A-Z0-9]{4}$/) {
						# not gonna return yet: probably it can be handled:
						# we have ended all DATA blocks, and this is a COVE text block
						$intermediate_state_marker='UNKNOWN';
						# and continue... later, $intermediate_state_marker 'll be checked. 
					} else {
						$self->_set_error(
							'Error: expecting first BKMK block in User Marks Area, '.
							'but '.unpack('H*',$buffer).' found'); # hexadecimal representation
						
						return 0;
					}
				}
			}

			##########
			# 20131109: PATCH: there're two consecutive pointers pointing to the same note!!!
			if ( tell(fMBP_file) > $index_table[$index_table_counter+1] ) { $index_table_counter++; }
			##########

			if ( # last block of file: this point can be reached here if 
				 # there's no user mark in this MBP file:
				 eof(fMBP_file) || 
				 ( ($index_table_counter < $#index_table) && 
				 # end of current block (but there're more coming):
				 tell(fMBP_file)==($index_table[$index_table_counter+1])) )
				{
				# store this DATA data in a DATA object, which will be
				# later associated to an appropriate MBP User Mark object.
				my $MBP_data_local=new MBP_User_Mark_DATA;
				$MBP_data_local->DATA($DATA_BUFFER);
				# (see next comment to understand this index_pointer assignment)
				$MBP_data_local->index_pointer( 
					$index_table{ $index_table[$index_table_counter] } 
				);
				# and we store it in a temporal hash (by identifier), 
				# 'til a BKMK blocks analysis can group them.
				# But, we need now the identifier for this DATA block...
				#   we don't know it: it's stored in %index_table, by 
				#   position pointer... but that "position pointer" is 
				#   returned by @index_table with $index_table_counter:
				$DATA{ 
					$index_table{ $index_table[$index_table_counter] } 
				} = $MBP_data_local;
				
				$DATA_BUFFER='';

				if ($intermediate_state_marker ne '') {
					# 20090622: empty DATAs should not be counted...
					if ($intermediate_state_marker ne 'EMPTY_DATA') {
						# store now the MBP_User_Mark: as it's not pointed
						# by any BKMK block, so it'd be lost:
						my $MBP_local=new MBP_User_Mark($intermediate_state_marker);
						# I think neither index order nor order in the book
						# have a meaning with a this type of Marks, so they'd be left unset.
						###$MBP_local->order(  );
						$MBP_local->DATA_insert( $MBP_data_local );
						push @{$self->{MBP_USER_MARKS}}, $MBP_local;
					}
					$intermediate_state_marker=''; # there can be more than 1...
				}

				if ($index_table_counter == $#index_table) {
					# last block of file: this point can be reached here if 
					# there's no user mark in this MBP file:
					# jump to end of file state
					$state_marker=10; # end of file state
				} else {
					# jump to next register
					$index_table_counter++;
				}
			}
		  }
			
		  #--------------------------------------
		  # BKMK state
		  elsif ($state_marker==7)
		  {
			if (tell(fMBP_file)==($index_table[$index_table_counter]+4) 
				&& $buffer ne 'BKMK') {
				$self->_set_error(
					'Error: expecting BKMK block in User Marks Area, '.
					' but '.unpack('H*',$buffer).' found'); # hexadecimal representation
				return 0;
			}

			$DATA_BUFFER.=$buffer;
			$self->{USER_MARKS_BKMK}.=$buffer;

			# parse BKMK contents: finally we can arrange the DATA blocks!
			###print unpack('H*',$buffer);
			# BKMK size:
			# BKMK beginning of text position:
			# BKMK end of text position:
			# BKMK ????
			# BKMK ????
			# BKMK type identifier (1/2):
			if (tell(fMBP_file)==($index_table[$index_table_counter]+24+4)) {
				my $bkmktype=unpack('H*',$buffer); ###switch (unpack('H*',$buffer)) {
					# 200912: MARK may also be 00... so I  comment this
					###case /(......)00/ { $BKMK_type='BOOKMARK'; } 
					# 201011: NOTE may also be 00... so I  comment this
					###case /(......)20/ { $BKMK_type='NOTE'; }
					# 201011: I'm gonna be also more cautious here:
					###case /(......)6f/ { $BKMK_type='CORRECTION'; }
					if ($bkmktype=~/(......).f/) { $BKMK_type='CORRECTION'; }
					# DRAWING and MARK share first BKMK type identifier!
					# (they'll be differenced by 2nd identifier):
					###case /(......)0f/ { $BKMK_type='DRAWING'; }
					# 200912: MARK may also be 00... so I  comment this, also.
					###case /(......)0f/ { $BKMK_type='MARK'; } 
					###else { 
					###	$self->_set_error(
					###			'BKMK Mark identifier unexpected '.
					###		unpack('H*',$buffer).
					###		' (not a recognised type).');
					###	return 0;
					###}
				###}
				# stores BKMK color, if the BKMK type uses it (DRAWING, for example)
				$buffer=~/^(...)/;
				$BKMK_color=unpack('H*',$1); 
			}
			# BKMK type identifier (2/2):
			if (tell(fMBP_file)==($index_table[$index_table_counter]+28+4)) {
				# 200912: marks can't be always anticipated, 
				#         so $BKMK_type must be set here, 
				#         except for (NOTE|CORRECTION):
				my $bkmktype=unpack('H*',$buffer); ###switch (unpack('H*',$buffer)) {
					if ($bkmktype eq '00000001') { 
						$BKMK_type='BOOKMARK';
					}
					elsif ($bkmktype eq '00000002') { 
						# 201011:
						###if ($BKMK_type !~ /^(NOTE|CORRECTION)$/) {
						###	$self->_set_error(
						###		'BKMK Mark identifier unexpected'.
						###		' (not a NOTE or CORRECTION).');
						###	return 0;
						###}
						if ($BKMK_type !~ /^CORRECTION$/) {
							$BKMK_type='NOTE';
						}
					}
					elsif ($bkmktype eq '00000004') { 
						$BKMK_type='MARK';
					}
					elsif ($bkmktype eq '00000008') {
						$BKMK_type='DRAWING';
					}
					else {
						# 200912: I'm not sure, but hope this cope with every possibility.
						$BKMK_type='UNKNOWN';
					}
				###}
			} # (BKMK type identifier (2/2))
			# BKMK data pointer 1
			if (tell(fMBP_file)==($index_table[$index_table_counter]+32+4)) {
				if (unpack('H*',$buffer) ne 'f'x8) {
					push @BKMK_pointers, unpack('N',$buffer); # big endian
				# 200912: I'm not sure, but hope 'UNKNOWN' cope with every possibility.
				} elsif ($BKMK_type !~ /^(?:BOOKMARK|NOTE|UNKNOWN)$/) {
					# (20080424: there're also NOTEs without stored marked text)
					$self->_set_error(
						'BKMK Mark identifier unexpected'.
						" ($BKMK_type ne BOOKMARK should have null pointer).");
					return 0;
				}
			}
			# BKMK data pointer 2
			if (tell(fMBP_file)==($index_table[$index_table_counter]+36+4)) {
				if (unpack('H*',$buffer) ne 'f'x8) {
					push @BKMK_pointers, unpack('N',$buffer); # big endian
					if ($BKMK_type =~ /^(DRAWING|MARK)$/) {
						$self->_set_error(
							'BKMK Mark identifier unexpected'.
							' (DRAWING or MARK should have null pointer).');
						return 0;
					}
				}
			}
			# BKMK data pointer 3
			if (tell(fMBP_file)==($index_table[$index_table_counter]+40+4)) {
				if (unpack('H*',$buffer) ne 'f'x8) {
					push @BKMK_pointers, unpack('N',$buffer); # big endian
				}
			}
			# BKMK data pointer 4
			if (tell(fMBP_file)==($index_table[$index_table_counter]+44+4)) {
				if (unpack('H*',$buffer) ne 'f'x8) {
					push @BKMK_pointers, unpack('N',$buffer); # big endian
					if ($BKMK_type ne 'DRAWING') {
						$self->_set_error(
							'BKMK Mark identifier unexpected'.
							' (only DRAWING should have this pointer)');
						return 0;
					}
				}
			}
			# BKMK FFFFFFFF
			# BKMK FFFFFFFF


			if ( eof(fMBP_file) || 
				 ( ($index_table_counter < $#index_table) && 
				 # end of current block (but there're more coming):
				 tell(fMBP_file)==($index_table[$index_table_counter+1])) )
				{

				# counts ( = the real order of objects in the book).
				$index_table_bkmk_marker++;

				# Now, we have enough data to fill a User Mark object:
				my $MBP_local=new MBP_User_Mark($BKMK_type);
				# sets the real order of objects in the book
				$MBP_local->order( $index_table_bkmk_marker );
				# from @BKMK_pointers, we know how many and which DATA blocks 
				# compone this User Mark.
				# And we have all DATA objects, arrange by identifier,
				# in %DATA.
				foreach (@BKMK_pointers) {
					$MBP_local->DATA_insert( $DATA{$_} );
				}
				# create now the BKMK objetc (sibling of a DATA object):
				my $MBP_bkmk_local=new MBP_User_Mark_BKMK;
				# insert raw BKMK data:
				$MBP_bkmk_local->BKMK( $DATA_BUFFER );
				# we need now the identifier for this BKMK block...
				#   we don't know it: it's stored in %index_table, by 
				#   position pointer... but that "position pointer" is 
				#   returned by @index_table with $index_table_counter:
				$MBP_bkmk_local->index_pointer( 
					$index_table{ $index_table[$index_table_counter] } 
				);
				# sets color, for future use (format: 0xRRGGBB):
				$MBP_bkmk_local->color($BKMK_color);
				# insert this BKMK object in the MBP User Mark object:
				$MBP_local->BKMK_insert( $MBP_bkmk_local );
				# and that's all!
				# we have in $BMP_local a complete MBP User Mark object
				# (its correct order will be later calculated)
				# so we put this in the MBP_USER_MARKS array:
				push @{$self->{MBP_USER_MARKS}}, $MBP_local;

				# reinitiate variables:
				$DATA_BUFFER='';
				$BKMK_type='';
				@BKMK_pointers=();

				if ($index_table_counter == $#index_table) {
					# last block of file: this point can be reached here if 
					# there's no user mark in this MBP file:
					# jump to end of file state
					$state_marker=10; # end of file state
				} else {
					# jump to next register
					$index_table_counter++;
				}
			} # (if ( eof(fMBP_file) || ...)
		  } # (elsif ($state_marker==7) # BKMK)

		  #--------------------------------------
		  # End of File state
		  elsif ($state_marker==10)
		  {
			# Job done.
			# while iteration will never enter this if/elsif block.
		  } # (elsif ($state_marker==10) # end of file)

		} # if/elsif (switch)
		#########################################

	} # (while (!eof(fMBP_file)) { ...)

	# Job done.

	# last duties:
	# calculate order of User Marks in the Index Table:
	foreach ( @{$self->{MBP_USER_MARKS}} ) {
		if ($_->type eq 'BPAR') {
			$_->index_order(0); # BPAR is always the first (0) in index table
		} elsif ($_->type ne 'CATE') {
			$_->index_order( 
				$#{$self->{MBP_USER_MARKS}}
				- ($_->order) + 1 # +1. 'cause 0 is always BPAR block.
			); 
		}
	}


	close fLog_file;
	close fMBP_file;
	undef $self->{FILE_DESCRIPTOR};
	
	return 1;
}


# returns version of MBP_Reader.pm
sub version {
	return '0.5.c';
}


# returns MBP_Reader.pm authoring string 
sub authoring {
	my ($self)=@_;
	return 
		"MBP file reader\nv".$self->version." (idleloop\@yahoo.com, 201311)\n".
		"http://www.angelfire.com/ego2/idleloop/\n\n";
}


1;