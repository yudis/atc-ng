#!/usr/bin/env python
# -*- coding: utf-8  -*-
'''
Provide functionality for entering commands and processing them.
'''

from locals import *
from pygame.locals import *
from collections import deque
from random import randint
from copy import copy
import pygame.font
import re
import time

__author__ = "Mac Ryan"
__copyright__ = "Copyright 2011, Mac Ryan"
__license__ = "GPL v3"
#__version__ = "1.0.0"
__maintainer__ = "Mac Ryan"
__email__ = "quasipedia@gmail.com"
__status__ = "Development"


GAME_COMMANDS = {'quit' : {'spellings': ['quit', 'q'],
                           'arguments': 0,
                           'validator': None,
                           'flags'    : []
                           },
                 'help' : {'spellings': ['help', 'h', 'man'],
                           'arguments': 0,
                           'validator': None,
                           'flags'    : []
                           }
                 }

PLANE_COMMANDS = {
        'heading'  : {'spellings': ['heading', 'h', 'head'],
                      'arguments': 1,
                      'validator': '_validate_heading',
                      'flags'    : {'expedite' : ['expedite', 'x'],
                                    'long_turn': ['l', 'long',]}},
        'altitude' : {'spellings': ['altitude', 'a', 'alt'],
                      'arguments': 1,
                      'validator': '_validate_altitude',
                      'flags'    : {'expedite': ['expedite', 'x']}},
        'speed'    : {'spellings': ['speed', 's', 'sp'],
                      'arguments': 1,
                      'validator': '_validate_speed',
                      'flags'    : {'expedite': ['expedite', 'x']}},
        'takeoff' : {'spellings': ['takeoff', 'to', 'up', 'fly'],
                      'arguments': 1,
                      'validator': '_validate_altitude',
                      'flags'    : {'expedite': ['expedite', 'x']}},
        'land'     : {'spellings': ['land', 'l', 'down'],
                      'arguments': 2,
                      'validator': '_validate_land',
                      'flags'    : []},
        'circle'   : {'spellings': ['circle', 'c', 'hold'],
                      'arguments': 1,
                      'validator': '_validate_circle',
                      'flags'    : []},
        'abort'    : {'spellings': ['abort', 'purge'],
                      'arguments': 0,
                      'validator': None,
                      'flags'    : {'lastonly': ['lastonly', 'last', 'l']}}
        }

VALID_PLANE_COMMANDS_COMBOS = [('heading', 'altitude', 'speed'),
                               ('circle', 'altitude', 'speed')]

AFFIRMATIVE_EXEC_ANSWERS = ['Roger that. Executing.',
                            'Affirmative, initiating maneuver now.',
                            'Roger, we\'re on it.',
                            'Copy that.',
                            'Okie dokie artichokie!']

AFFIRMATIVE_QUEUE_ANSWERS = ['Roger that. Queued.',
                             'Affirmative, command queued for execution.',
                             'We\'ll do that as soon as possible.',
                             'Copy that, command queued']


class Parser(object):

    '''
    Parse a command line (validate and execute it).
    '''

    def __init__(self, aerospace):
        self.aerospace = aerospace
        self.initialise()

    def initialise(self, sentence=''):
        '''
        The parser object is reusable. This method resets the parser internal
        status and set the text to a given value.
        '''
        # If present, separate control character from command with a space
        if len(sentence) > 1 and sentence[0] in './' and sentence[1] != ' ':
            sentence = sentence[0] + ' ' + sentence[1:]
        self.sentence = sentence
        self.validated = False
        self.bits = []                   #the sentence, reversed and split
        self.target = None               #plane that should receive order

    # VALIDATORS These methods provide validation for the arguments of the
    # commands. All arguments are passed-in as strings and are converted to a
    # suitable format during the validation process. The methods return False
    # if the argument fails validation, or a list containing the converted ones
    # if passes.

    def _validate_icao(self, icao):
        '''
        Valid plane designations are in the format `XXX0000` with `X` being
        letters and `0` being digits.
        '''
        if None == re.match(r'^[a-zA-Z]{3}\d{4}$', icao):
            return False
        return [icao.upper()]

    def _validate_heading(self, heading):
        '''
        Valid headings can be either a 3 digit angle between 000° and 360° or a
        beacon code.
        '''
        try:
            num_h = int(heading)
        except ValueError:
            return False
        if not 0 <= num_h <= 360 and len(heading) == 3:
            return False
        return [num_h]

    def _validate_altitude(self, altitude):
        '''
        Valid altitudes are given in hundreds of meters, and are multiple of
        500. They must also be in the range between min and max altitudes for
        the game.
        '''
        #TODO: Parametrise the min and max in-game altitudes
        try:
            num_a = int(altitude)
        except ValueError:
            return False
        if not 0 <= num_a <= 80 and len(altitude) == 2 and num_a % 5 == 0:
            return False
        return [num_a * 100]  #return in metres

    def _validate_speed(self, speed):
        '''
        Valid speeds are given in hundreds of km/h.
        '''
        try:
            num_s = int(speed)
        except ValueError:
            return False
        return [rint(num_s / 3.6)]  #return in metres/second

    def _validate_land(self, iata, runaway):
        '''
        Valid landings indicate the three-letters airport code and the runaway
        in the format 00X, where 0 represent a digit and X a letter (R,L or C)
        '''
        return (not (None == re.match(r'^[a-zA-Z]{3}$', iata)) and
                not (None == re.match(r'^\d{2}(L|C|R)?$', runaway)))

    def _validate_circle(self, direction):
        '''
        Parameter can only be right (r) or left (l).
        '''
        if direction.lower() not in ('r', 'right', 'cw', 'l', 'left', 'ccw'):
            return False
        return [direction]

    def parse(self):
        '''
        Validate/Parse the command line.
        Returns a list of parsed commands in case of success, or a string with
        an error message in case of failure.
        The parsed commands list is structured with a callable object and a
        list that should be given as input for it:
        [[callable_, [arg1, arg2...]], [callable_, [arg1, arg2]]]
        '''
        if len(self.sentence) == 0:
            return []
        self.bits = self.sentence.lower().split()
        self.bits.reverse()
        first = self.bits.pop()
        # We're issuing commands to a plane
        if self._validate_icao(first):
            return self.parse_plane_commands(first)
        # We're appending commands to a plane queue
        elif first[0] == '.':
            icao = self.bits.pop()
            if self._validate_icao(icao):
                return self.parse_plane_commands(icao, to_queue=True)
            else:
                msg = '"%s" is not a valid ICAO reference.' % icao.upper()
                return msg
        # We're issuing a game command
        elif first == '/':
            return self.parse_game_command()
        else:
            msg = '"%s" is not a valid ICAO reference.' % first.upper()
            return msg

    def parse_plane_commands(self, icao, to_queue=False):
        '''
        Parse all commands on the command line, dispatching them to the plane
        whose ICAO code is given.
        '''
        parsed_commands = []
        aeroplane = self.aerospace.get_plane_by_icao(icao)
        callable_ = aeroplane.queue_command if to_queue \
                                            else aeroplane.execute_command
        while len(self.bits) != 0:
            # The first bit of a command sequence is either the command or
            # the condensed form for heading, altitude and speed (see below)
            issued = self.bits.pop()
            # Special condensed syntax is allowed for H, A, S in the form
            # letter+digits without spaces
            decomposed = re.match(r'^(h|s|a)(\d{2,})$', issued)
            if decomposed:
                c = decomposed.group(1)
                a = decomposed.group(2)
                if c == 'h' and self._validate_heading(a) or \
                   c == 'a' and self._validate_altitude(a) or \
                   c == 's' and self._validate_speed(a):
                    issued = c
                    self.bits.append(a)
            # Identify the issued command
            command_name = None
            command = None
            for k, v in PLANE_COMMANDS.items():
                if issued in v['spellings']:
                    command_name = k
                    command = v
                    break
            if not command_name or not command:
                msg = '"%s" is neither a command nor a flag.' % issued.upper()
                return msg
            # Parse arguments
            args = []
            for i in range(command['arguments']):
                try:
                    args.append(self.bits.pop())
                except IndexError:
                    msg = 'Not enough arguments for command "%s".' % \
                            command_name.upper()
                    return msg
            # Verify that arguments pass validation
            if command['validator']:
                validator = getattr(self, command['validator'])
                args = validator(*args)
                if not args:
                    msg = 'Parameters for "%s" command failed validation.' % \
                            command_name.upper()
                    return msg
            # Check for flags and parse them if present
            flags = []
            possible_flag = command['flags']  #[] = skip
            while possible_flag:
                possible_flag = False
                if not self.bits:
                    break
                candidate = self.bits[-1]
                for k, v in command['flags'].items():
                    if candidate in v:
                        flags.append(k)
                        self.bits.pop()
                        possible_flag = True
                        break
            # Store the parsed commands
            parsed_commands.append([command_name, args, flags])
        # Verify that some command has been entered
        if len(parsed_commands) == 0:
            msg = 'No commands were issued to the plane.'
            return msg
        # FINAL SEMANTIC CHECKS
        command_list = [el[0] for el in parsed_commands]
        command_set = set(command_list)
        # If they are to be queued, does it makes sense?
        if callable_.__name__ == 'queue_command' and \
                   'abort' in command_list:
            msg = 'You can\'t queue abortion of a command.'
            return msg
        # If several commands are issued at once, verify they are compatible
        elif len(parsed_commands) != 1:
            # No duplicates!
            if len(command_list) != len(command_set):
                msg = 'You can\'t repeat commands in the same transmission.'
                return msg
            valid = False
            # Can be logically mixed
            for combo in VALID_PLANE_COMMANDS_COMBOS:
                if command_set <= set(combo):
                    valid = True
            if not valid:
                msg = 'These commands cannot be performed at the same time.'
                return msg
        return (callable_, parsed_commands)

    def parse_game_command(self, validate_only=False):
        command = self.bits.pop()
        if command in GAME_COMMANDS['quit']['spellings']:
            print('quit')
        elif command in GAME_COMMANDS['help']['spellings']:
            print('help')
        else:
            msg = 'Invalid game command! (%s)' % command.upper()
            return msg
        return []

class CommandLine(object):

    '''
    This class manage the command string composition, validation, etc...
    '''

    def __init__(self, surface, aerospace):
        self.chars = list('')
        self.surface = surface
        self.aerospace = aerospace
        # Properties for handling multiline console and history browsing
        self.command_history = []
        self.history_ptr = 0
        self.console_lines = deque(maxlen=CONSOLE_LINES_NUM)
        self.console_image = pygame.surface.Surface((0,0))
        self.last_console_snapshot = copy(self.console_lines)
        self.cmd_prefix = ' '.join((OUTBOUND_ID, PROMPT_SEPARATOR))
        # Pygame font initialisation
        if not pygame.font.get_init():
            pygame.font.init()
        # Font size calculations
        small_size = CLI_RECT.h * 0.9 / \
                     (CONSOLE_LINES_NUM + 1.0/CONSOLE_FONT_SIZE_RATIO)
        large_size = rint(small_size / CONSOLE_FONT_SIZE_RATIO)
        small_size = rint(small_size)
        file_ = '../data/ex_modenine.ttf'
        self.large_f = pygame.font.Font(file_, large_size)
        self.small_f = pygame.font.Font(file_, small_size)
        self.parser = Parser(aerospace)

    def __randomel(self, list_):
        '''
        Return the random element of a list
        '''
        return list_[randint(0, len(list_)-1)]

    def _get_list_of_existing(self, what, context=None):
        '''
        Return a list of existing (=valid) strings representing `what`
        ('planes', 'aeroports', 'runaways' or 'beacons'). The `contex` value
        is used for those `what` which are not global to the aerospace (e.g.:
        runaways can be given for a given aeroport, not aerospace).
        '''
        if what == 'planes':
            return [p.icao for p in self.aerospace.aeroplanes]
        elif what == 'plane_commands':
            return [key for key in PLANE_COMMANDS.keys()]
        elif what == 'aeroports':
            return [a.iata for a in self.aerospace.aeroports]
        elif what == 'runaways':
            assert context != None  #Context must be the name of the aeroport
            for ap in self.aerospace.aeroports:
                if ap.iata == context:
                    return [r.id for r in ap.runaways]
            return []
        elif what == 'beacons':
            return [b.code for b in self.aerospace.beacons]
        elif what == 'game_commands':
            return [key for key in GAME_COMMANDS.keys()]
        else:
            raise BaseException('Unknown type of items: %s!' % what)

    def _get_common_beginning(self, strings):
        '''
        Return the strings that is common to the beginning of each string in
        the strings list.
        '''
        result = []
        limit = min([len(s) for s in strings])
        for i in range(limit):
            chs = set([s[i] for s in strings])
            if len(chs) == 1:
                result.append(chs.pop())
            else:
                break
        return ''.join(result)

    @property
    def text(self):
        return ''.join(self.chars)

    def autocomplete(self):
        splitted = self.text.lower().split()
        spl_len = len(splitted)
        what = None
        context = None
        # get the last three bits, if available
        root, pre, prepre = None, None, None
        if spl_len > 0:
            root = splitted[-1]
        if spl_len > 1:
            pre = splitted[-2]
        if spl_len > 2:
            prepre = splitted[-3]
        # identify what is the context of autocompletion
        if self.chars[0] == '/':
            what = 'game_commands'
        elif spl_len == 2 and self.chars[0] == '.' or \
             root == self.text.lower():
            root = root.upper()
            what = 'planes'
        elif pre:
            if self.parser._validate_icao(pre):
                what = 'plane_commands'
            # the argument of circling can be 'L' (left) which could be
            # understood as the shorthand for 'LAND'
            elif pre in PLANE_COMMANDS['land']['spellings'] and \
                 prepre not in PLANE_COMMANDS['circle']['spellings']:
                what = 'aeroports'
            elif pre in PLANE_COMMANDS['heading']['spellings']:
                what = 'beacons'
            elif prepre:
                if prepre in PLANE_COMMANDS['land']['spellings']:
                    what = 'runaways'
                    context = pre.upper()
                elif (self.parser._validate_icao(splitted[0]) or \
                     self.parser._validate_icao(splitted[1])) and \
                     pre not in PLANE_COMMANDS.keys():
                    what = 'plane_commands'
        if not what:
            return
        pool = self._get_list_of_existing(what, context)
        matches = [i.upper() for i in pool if i.find(root) == 0]
        if len(matches) == 1:
            match = matches[0]+' '
        elif len(matches) > 1:
            match = self._get_common_beginning(matches)
        else:
            return
        self.chars.extend(list(match[len(root):]))

    def process_keystroke(self, event):
        mods = pygame.key.get_mods()
        if event.key == K_RETURN:
            self.parser.initialise(self.text)
            parsed = self.parser.parse()
            # If an empty line has been parsed, skip everything
            if parsed == []:
                return
            # Fail to parse generate a string (an iterable if successful)
            if type(parsed) in (unicode, str):
                answer_prefix = 'You are doing it wrong! '
                self.console_lines.append([RED, answer_prefix+parsed])
            else:
                # Successfully parsed commands are echoed on console and added
                # to command history...
                self.console_lines.append([WHITE,
                                        ' '.join((self.cmd_prefix,self.text))])
                self.command_history.insert(0, self.text)
                # ...executed...
                callable_, args = parsed
                ret = callable_(args)
                # ...their answer is displayed on the console...
                fname = callable_.__name__
                colour = GREEN
                if fname in ('execute_command', 'queue_command'):
                    icao = callable_.im_self.icao
                    answer_prefix = ' '.join((icao, PROMPT_SEPARATOR))
                    if ret == True:
                        if fname == 'execute_command':
                            answer = self.__randomel(AFFIRMATIVE_EXEC_ANSWERS)
                        elif fname == 'queue_command':
                            answer = self.__randomel(AFFIRMATIVE_QUEUE_ANSWERS)
                    else:
                        answer = ret
                        colour = RED
                else:
                    #TODO: game commands processing
                    pass
                self.console_lines.append([colour,
                                           ' '.join((answer_prefix,answer))])
                # ...and the command line is finally emptied for a new command
                self.chars = []
        elif event.key == K_ESCAPE:
            self.chars = []
        elif event.key == K_BACKSPACE and self.chars:
            self.chars.pop()  #one char is taken away in any case
            if mods & KMOD_LCTRL:
                while self.chars and self.chars.pop() != ' ':
                    pass
        elif event.key == K_TAB:
            self.autocomplete()
        elif event.key == K_UP and \
                            self.history_ptr < len(self.command_history):
            self.chars = list(self.command_history[self.history_ptr])
            self.history_ptr += 1
        elif event.key == K_DOWN:
            if self.history_ptr > 1:
                self.history_ptr -= 1
                self.chars = list(self.command_history[self.history_ptr-1])
            elif self.history_ptr == 1:
                self.chars = []
                self.history_ptr = 0
        elif event.unicode in VALID_CHARS:
            # No unintentional spaces (issued by appending empty chars due
            # to modifiers keys)
            if event.unicode == '':
                return
            # No leading spaces, no double spaces
            if event.unicode == ' ' and \
               (len(self.chars) == 0 or self.chars[-1] == ' '):
                return
            self.chars.append(event.unicode.upper())
            # command modifiers from commands
            if event.unicode in './':
                self.chars.append(' ')

    def _render_console_lines(self):
        '''
        Return the image of the rendered multiline text.
        Lines are passed in the format: [color_of_text, text].
        '''
        lines = self.console_lines
        font_height = self.small_f.get_height()
        surfaces = [self.small_f.render(txt, True, col) for col, txt in lines]
        maxwidth = max([s.get_width() for s in surfaces])
        result = pygame.surface.Surface((maxwidth, len(lines)*font_height),
                                        SRCALPHA)
        for i in range(len(lines)):
            result.blit(surfaces[i], (0,i*font_height))
        return result

    def draw(self):
        # Basic blinking of cursor
        cursor = '_' if int(time.time()*2) % 2 else ''
        # Re-drawing of the console lines is only done if the console lines
        # have changed since last iteration
        if self.last_console_snapshot != self.console_lines:
            self.last_console_snapshot = copy(self.console_lines)
            self.console_image = self._render_console_lines()
        image = self.large_f.render(self.text + cursor, True, WHITE, BLACK)
        sw, sh = self.surface.get_size()
        x = sw*0.01
        y = sh*0.03
        self.surface.fill(BLACK)
        self.surface.blit(self.console_image, (x,y))
        self.surface.blit(image,
                          (x, 2*y+self.small_f.get_height()*CONSOLE_LINES_NUM))