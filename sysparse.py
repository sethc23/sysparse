
import os, re, inspect, fileinput
import argcomplete, argparse, argh
from sys import argv
from subprocess import Popen as sub_popen
from subprocess import PIPE as sub_PIPE
import types as TYPES
from argh.decorators import *
from argcomplete.completers import ChoicesCompleter

# Commented this while loading http://ipy.sanspaper.com/notebooks/GOOGLE_API.ipynb#
# from sys_reporter import sys_reporter

global pgsql_queries,choices
pgsql_queries = {}
choices = {}

in_args = argv if not os.environ.has_key('COMP_LINE') else os.environ['COMP_LINE'].split()
DEBUG_PARSING=False


def basic_components():
    from importlib import import_module
    _this_file          =   __file__[__file__.rfind('/') + 1:]
    _this_mod           =   _this_file[:-3] if _this_file[-2:]=='py' else _this_file[:-4]
    _mod                =   import_module(_this_mod)
    _components         =   []
    for it in inspect.getmembers(_mod, inspect.isfunction):
        _components.append(it)

    for it in inspect.getmembers(_mod, inspect.isclass):
        _components.append(it)

    return _components

def result_choices():
    if choices.has_key('result'):
        return choices['result']

    from sys_reporter import sys_reporter
    res = [name.lstrip('_') for name,fx
             in inspect.getmembers(sys_reporter,inspect.ismethod)
             if (name.find('_')==0 and name.find('__')==-1)]
    choices['result'] = res
    return res


def arg_custom(*args, **kwargs):
    from argh.constants import ATTR_ARGS
    from argh.assembling import _get_args_from_signature

    def wrapper(func):
        declared_args = getattr(func, ATTR_ARGS, [])
        for a in list(_get_args_from_signature(func)):
            opt_strs = [ it for it in a['option_strings'] if it != 'self' ]
            if opt_strs:
                declared_args.insert(0, dict(option_strings=opt_strs, help='(default: %(default)s)'))

        setattr(func, ATTR_ARGS, declared_args)
        return func

    return wrapper


def arg_basic(*args, **kwargs):
    from argh.constants import ATTR_ARGS
    from argh.assembling import _get_args_from_signature

    def wrapper(func):
        declared_args = getattr(func, ATTR_ARGS, [])
        for a in list(_get_args_from_signature(func)):
            opt_strs = [ it for it in a['option_strings'] if not ['self', 'args', 'kwargs'].count(it) ]
            if opt_strs:
                i_trace()
                declared_args.insert(0, dict(option_strings=opt_strs, help='(default: %(default)s)'))

        # for it in ['action','default','choices']:
        #     if declared_args.has_key(it):
        #         del declared_args[it]

        setattr(func, ATTR_ARGS, declared_args)
        return func

    return wrapper


def arg_by_pgsql(*args, **kwargs):
    from argh.constants import ATTR_ARGS
    from argh.assembling import _get_args_from_signature

    def wrapper(func):
        declared_args = getattr(func, ATTR_ARGS, [])
        run_qry = True
        if parsed_args:
            run_qry, qry_vars = False, []
            for it in parsed_args:
                if in_args.count(it):
                    idx = in_args.index(it)
                    qry_vars.append(in_args[idx + 1])

            if len(qry_vars) == len(parsed_args):
                query = query % tuple(qry_vars)
                run_qry = True
        if not run_qry or query.count('%s'):
            return []
        cmd = 'curl --get "http://%s:9999/qry" --data-urlencode "qry=%s" 2> /dev/null ;'
        _out, _err = sub_popen(cmd % (DB_HOST, query.replace('\n', '')), stdout=sub_PIPE, shell=True).communicate()
        assert _err is None
        try:
            j_res = eval(_out)
        except:
            print 'ERROR -- dropping to ipy'
            i_trace()

        # for it in ['action','default','choices']:
        #     if declared_args.has_key(it):
        #         del declared_args[it]

        setattr(func, 'res', sorted([ it['res'] for it in j_res ]))
        return func

    return wrapper


def arg_by_shell(*args, **kwargs):
    from argh.constants import ATTR_ARGS
    from argh.assembling import _get_args_from_signature

    def wrapper(func):
        declared_args = getattr(func, ATTR_ARGS, [])
        run_cmd = True
        if parsed_args:
            run_cmd, cmd_vars = False, []
            for it in parsed_args:
                if in_args.count(it):
                    idx = in_args.index(it)
                    cmd_vars.append(in_args[idx + 1])

            if len(cmd_vars) == len(parsed_args):
                cmd = cmd % tuple(cmd_vars)
                run_cmd = True
        if not run_cmd:
            RES = []
         # os.system(                                     "logger -t 'PY_PARSE_EXEC_1' '%s'" % str(cmd))
        _out, _err = sub_popen(cmd.replace('\n', ''), stdout=sub_PIPE, shell=True).communicate()
        assert _err is None
        RES = _out
        # for it in ['action','default','choices']:
        #     if declared_args.has_key(it):
        #         del declared_args[it]
        setattr(func, 'res', RES)
        return func

    return wrapper


def get_default_args(self, func):
    """
    returns a dictionary of arg_name:default_values for the input function
    """
    args, varargs, keywords, defaults = inspect.getargspec(func)
    return dict(zip(args[-len(defaults):], defaults))


def add_arg_help(parser):
    parser.add_argument('--help', action='help', help='show this help message and exit')
    return parser


class Store_List(argparse.Action):

    def __init__(self, option_strings, dest, nargs = None, **kwargs):
        if nargs is not None:
            raise ValueError('nargs not allowed')
        super(Store_List, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string = None):
        try:
            _out = eval(values)
        except:
            _out = values.strip('[]').split(',')

        setattr(namespace, self.dest, _out)


class Store_File(argparse.Action):

    def __init__(self, option_strings, dest, nargs = None, **kwargs):
        if nargs is not None:
            raise ValueError('nargs not allowed')
        super(Store_File, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string = None):
        # print '%r %r %r' % (namespace, values, option_string)
        # try:
        # def hook_nobuf(filename, mode):
        #     return open(filename, mode, 0)
        global input_text
        print 'here too'
        if values:
            import fileinput
            fd_stdin, input_text = fileinput.input('-'), []
            while True:
                f_descr_1 = fd_stdin.fileno()
                line = ''.join([ seg for seg in fd_stdin.readline() ]).strip('\n')
                f_descr_2 = fd_stdin.fileno()
                if f_descr_1 == f_descr_2 == -1 or fd_stdin.lineno() == 0:
                    break
                if line:
                    print line
                    input_text.append(line)

            _out = input_text
        else:
            _out = []
        setattr(namespace, self.dest, _out)


def parse_choices_from_class():
    i_trace()


def parse_choices_from_exec(cmd, parsed_args = []):
    run_cmd = True
    if parsed_args:
        run_cmd, cmd_vars = False, []
        for it in parsed_args:
            if in_args.count(it):
                idx = in_args.index(it)
                cmd_vars.append(in_args[idx + 1])

        if len(cmd_vars) == len(parsed_args):
            cmd = cmd % tuple(cmd_vars)
            run_cmd = True
    if not run_cmd:
        return []
    # os.system(                                     "logger -t 'PY_PARSE_EXEC_1' '%s'" % str(cmd))
    _out, _err = sub_popen(cmd.replace('\n', ''), stdout=sub_PIPE, shell=True).communicate()
    assert _err is None
    return _out


def parse_choices_from_pgsql(query, parsed_args = []):
    global pgsql_queries
    query = re.sub('[\\s]{2,}', ' ', query).strip()
    if pgsql_queries.has_key(query):
        return pgsql_queries[query]
    from system_settings import DB_HOST
    run_qry = True
    if parsed_args:
        run_qry, qry_vars = False, []
        for it in parsed_args:
            if in_args.count(it):
                idx = in_args.index(it)
                qry_vars.append(in_args[idx + 1])

        if len(qry_vars) == len(parsed_args):
            query = query % tuple(qry_vars)
            run_qry = True
    if not run_qry or query.count('%s'):
        return []
    cmd = 'curl -s http://%s:9999/curl_query?qry="%s" 2> /dev/null;'
    cmd = re.sub('[\\s]{2,}', ' ', cmd % (DB_HOST, query)).strip()
    _out, _err = sub_popen(cmd, stdout=sub_PIPE, shell=True).communicate()
    assert _err is None
    try:
        j_res = eval(_out)
        this_res = sorted([ it['res'] for it in j_res ])
        pgsql_queries[query] = this_res
        return this_res
    except:
        print 'ERROR -- dropping to ipy'
        import ipdb as I; I.set_trace()


def parser_completer(prefix, parsed_args, **kwargs):
    # os.system(                             "logger -t 'PY_PARSE_COMPLETER' '%s'" % prefix )
    # os.system(                             "logger -t 'PY_PARSE_COMPLETER' '%s'" % parsed_args)
    # os.system(                             "logger -t 'PY_PARSE_COMPLETER' '%s'" % kwargs )
    # os.system(                             "logger -t 'PY_PARSE_COMPLETER' '%s'" % kwargs['action'].choices )
    return (it for it in kwargs['action'].choices if it.find(prefix) == 0)


def parse_function(class_func, parser, in_args):
    if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno,'parse_function'
    p, THIS_ARG, last_args = parser, in_args[0], []
    in_args = in_args[1:]
    non_help_in_args = [ it for it in in_args if not it=='--help' ]
    p.description = class_func.__doc__
    p.usage = '\n\t' + ' '.join([p.usage.replace(' [--help]', '').strip('\n'), THIS_ARG])
    pre_existing_args = p.usage.split()[1:]
    # Special Case (need to include default arg when parsing command line)
    if single_class:
        pre_existing_args = [single_class,THIS_ARG]
    t = inspect.stack()[:]
    t.reverse()
    for it in t:
        if it[3] == 'parse_function':
            arg_specs = inspect.getargspec(inspect.getargvalues(it[0]).locals['class_func'])
            if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
            break

    # if hasattr(class_func,'argh_args'):
    arg_defaults = None if not arg_specs.defaults else dict(zip(arg_specs.args[-len(arg_specs.defaults):], arg_specs.defaults))
    for i in range(len(class_func.argh_args)):
        if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno,'(iter) ARG_NUM:',i
        arg_name, arg_names, arg_val = (None, None, None)
        arg_val_is_null = False
        it = dict(class_func.argh_args[i])
        if it.has_key('completer'):
            it['choices'] = it['completer']
            if not os.environ.has_key('COMP_LINE'):
                del it['completer']
        
        # Get Arg Info
        arg_names = it['option_strings']
        if not len(arg_names):
            return p.parse_args(pre_existing_args + [THIS_ARG])
            # break
        arg_name = arg_names[0]

        # Get Value of Positional Arg (if any)
        if not arg_name[0] == '-':
            if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
            if i > len(non_help_in_args) - 1:
                arg_val = ''
            else:
                arg_val = non_help_in_args[i]
                if not arg_val:
                    arg_val_is_null = True

        # Special Case for Piped Data
        elif it.has_key('dest') and it['dest'] == 'input':
            if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
            if globals().has_key('input_text') and input_text:
                arg_val = input_text
                idx = in_args.index('---')
                last_args.extend([in_args.pop(idx), input_text])
            else:
                if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
                arg_val_is_null = True
                
        # Get Value of Optional Arg (if any)
        else:
            if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
            for _arg in arg_names:
                if non_help_in_args.count(_arg):
                    idx = non_help_in_args.index(_arg)
                    try:
                        arg_val = non_help_in_args[idx + 1]
                    except:
                        print it
                        print _arg
                        import ipdb as I; I.set_trace()

                    if not arg_val:
                        arg_val_is_null = True
                    break

        del it['option_strings']

        # CASE: arg value in command line
        #   include arg in usage
        #   suppress help

        if arg_val:
            if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
            it['help'] = argparse.SUPPRESS
            p.usage += ' ' + arg_val
            # CASE: if arg_val is not contained in choices, e.g., partial arg val
            if it.has_key('choices'):
                if not it['choices'].count(arg_val):
                    tmp_p = argcomplete.argparse.ArgumentParser(add_help=False)
                    tmp_p.add_argument(*arg_names, **it).completer = parser_completer
                    tmp_p = add_arg_help(tmp_p)
                    argcomplete.autocomplete(tmp_p)
        # CASE: no arg value in command line
            #   (generally):
            #       add line with CHOICES if applicable
            #       add line with DEFAULT
            #
            #   usage:
            #       if positional, make all caps
            #       if optional, enclose with brackets
            #
            #   positional help text:
            #       use arg_name.upper() as metavar
            #       
            #   optional help text:
            #       if applicable, add line "NOTE: argument can be specified multiple times"
            # 
        else:
            if not arg_names[0][0] == '-' and not arg_name[0] == '-':
                if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
                p.usage += ' ' + arg_name.upper()
                it['metavar'] = arg_name.upper()
                if it.has_key('type'):
                    print 'last_here'
                # if, while iterating through current command line arg, 
                #   a positional argument is reached without a value,
                #   create temp. parser and run autocomplete function for said positional arg
                tmp_p = argcomplete.argparse.ArgumentParser(add_help=False)
                tmp_p.add_argument(*arg_names, **it).completer = parser_completer
                tmp_p = add_arg_help(tmp_p)
                argcomplete.autocomplete(tmp_p)
            else:
                if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
                p.usage += ' [%s]' % arg_name
                if it.has_key('choices'):
                    it['metavar'] = ''
                if it.has_key('default') and arg_name[0] == '-':
                    if type(it['default']) == list:
                        in_args.append(arg_name)
                        for a in it['default']:
                            in_args.append(a)

                    else:
                        in_args.extend([arg_name, it['default']])
            if it.has_key('help'):
                if it.has_key('action') and it['action'] == 'append':
                    it['help'] += '\nNOTE: argument can be specified multiple times'
                if it.has_key('choices'):
                    it['help'] += '\nCHOICES: %s' % str(it['choices']).strip('[]')
                if it.has_key('default'):
                    it['help'] += '\nDEFAULT: %s' % it['default']
        if it.has_key('default') and not in_args and not arg_name[0] == '-':
            in_args.append(it['default'])

        # Removing null values from command line
        if arg_val_is_null:
            if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
            if in_args.count(arg_name):
                idx = in_args.index(arg_name)
                i_trace()
                z = in_args.pop(idx)
                z = in_args.pop(idx)
        else:
            if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
            p.add_argument(*arg_names, **it)

    if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno,'(iter end)'
    p.usage += ' [--help]\n'
    # If Class/Module only has one function, the function is called by default but need not show in usage
    if single_function:
        if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
        p.usage = p.usage.replace(' %s ' % single_function, ' ')
    if not in_args or os.environ.has_key('COMP_LINE'):
        if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
        argcomplete.autocomplete(p)
        import ipdb as I; I.set_trace()
        return p.parse_known_args()
        # return argh.dispatch(p)
    if in_args.count('--help'):
        if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
        p.print_help()
        exit(1)
    else:
        if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
        # print pre_existing_args + in_args + last_args
        # i_trace()

        # if os.environ.has_key('COMP_LINE'):
        #     os.system(                         "logger -t 'PY_PARSE_F2' '%s'" % str('>>'+os.environ['COMP_LINE']+'<<'))
        # else:
        #     os.system(                         "logger -t 'PY_PARSE_F2' '%s'" % str('>>'+str(in_args)+'<<'))
        
        if single_class and single_function and in_args == [single_function]:
            if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
            return class_func()
        # import ipdb as I; I.set_trace()
        
        return p.parse_args(pre_existing_args + in_args + last_args)


def parse_module_or_class(mod_class, parser, in_args, parse_type = 'class'):
    if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno,'parse_module_or_class'
    global single_function
    p = parser
    non_help_in_args = [ it for it in in_args if not it == '--help' ]
    # function is being pulled from command line
    in_args = in_args if in_args == ['--help'] else in_args[1:]
    THIS_ARG = '' if not non_help_in_args else non_help_in_args[0]
    p.description = mod_class.__doc__
    p.usage = p.format_usage().rstrip(' [--help] \n').replace('usage: ', '') + ' ' + THIS_ARG + ' [--help]\n'
    if parse_type == 'class':
        fxs = [ name for name, fx in inspect.getmembers(mod_class, inspect.ismethod) if hasattr(fx, 'argh_args') ]
    elif parse_type == 'module':
        fxs = [ name for name, fx in inspect.getmembers(mod_class, inspect.isfunction) if hasattr(fx, 'argh_args') ]
        # fxs                                 =   [name for name,fx in inspect.getmembers(mod_class,inspect.isfunction)]
    # If single-class, clean usage
    if no_class or single_class:
        p.usage = p.usage.replace(' %s ' % THIS_ARG, ' ')
    # If Class only has one function, this function is called by default
    if len(fxs) == 1:
        single_function = fxs[0]
        if not in_args == ['--help']:
            in_args.insert(0, single_function)
    else:
        single_function = False
    # Parsing Class Ends Here
    if not in_args or in_args == ['--help']:
        sp = p.add_subparsers()
        for it in fxs:
            sp.add_parser(it, help=getattr(mod_class, it).__doc__)
        # if os.environ.has_key('COMP_LINE'):
        #     os.system(                         "logger -t 'PY_PARSE_C1' '%s'" % str('>>'+os.environ['COMP_LINE']+'<<'))
        # else:
        #     os.system(                         "logger -t 'PY_PARSE_C1' '%s'" % str('>>'+str(in_args)+'<<'))
        p.usage = '\n\t' + p.format_usage().replace('usage: ', '', 1).replace('[--help]', '').replace(' ... ', '').rstrip(' \n')
        sp.metavar = 'FUNCTION'
        p.usage += ' %s [--help]' % sp.metavar
        argcomplete.autocomplete(p)
        if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
        return p.parse_args()
    # Unrecognized Parse instruction
    if in_args and not fxs.count(in_args[0]):
        argcomplete.autocomplete(p)
        print 'Unrecognized <function>'
        print in_args
        p.print_help()
        if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
        exit(1)
    # Execute Parse instruction
    else:
        # if os.environ.has_key('COMP_LINE'):
        #     os.system(                         "logger -t 'PY_PARSE_C3' '%s'" % str('>>'+os.environ['COMP_LINE']+'<<'))
        # else:
        #     os.system(                         "logger -t 'PY_PARSE_C3' '%s'" % str('>>'+str(in_args)+'<<'))
        #     os.system(                         "logger -t 'PY_PARSE_C3' '%s'" % str('>>'+str(p.usage)+'<<'))
        p_help = argparse.SUPPRESS if [ it for it in in_args if not it == '--help' ] else mod_class.__doc__
        p.add_argument('_func', choices=fxs, help=p_help)
        if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
        return parse_function(getattr(mod_class, in_args[0]), p, in_args)


def parse_module(mod_path, regex, excludes):
    if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno,'parse_module'
    global no_class, single_class, mod
    in_args = argv if not os.environ.has_key('COMP_LINE') else os.environ['COMP_LINE'].split()
    in_args = in_args[1:]
    import imp
    mod = imp.load_source('', mod_path)
    avail_classes = {}
    for k, v in mod.__dict__.iteritems():
        if regex and re.findall(regex, k) and inspect.isclass(v) and not excludes.count(k):
            avail_classes.update({k: re.sub(regex, '\\1', k.lower())})
        elif not regex and inspect.isclass(v) and not v.__module__ and not excludes.count(k):
            avail_classes.update({k: k.lower()})

    # Check input args and use autocomplete for partial args
    if in_args and (not in_args[0] == '--help' or not avail_classes.values().count(in_args[0])):
        # if os.environ.has_key('COMP_LINE'):
        #     os.system(                         "logger -t 'PY_PARSE_M1' '%s'" % str('>>'+os.environ['COMP_LINE']+'<<'))
        # else:
        #     os.system(                         "logger -t 'PY_PARSE_M1' '%s'" % str('>>'+str(in_args)+'<<'))
        tmp_p = argcomplete.argparse.ArgumentParser(add_help=False)
        tmp_p.add_argument('function_class', choices=avail_classes.values()).completer = parser_completer
        tmp_p = add_arg_help(tmp_p)
        argcomplete.autocomplete(tmp_p)
    p = argparse.ArgumentParser(description=mod.__doc__, formatter_class=argparse.RawTextHelpFormatter, add_help=False)
    p = add_arg_help(p)
    # If no classes, send to parse as 'module'
    if len(avail_classes.values()) == 0:
        no_class, single_class = True, False
        if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
        return parse_module_or_class(mod, p, in_args, 'module')
    # If Module only has one Class, this Class is called by default
    if len(avail_classes.values()) == 1:
        no_class = False
        single_class = avail_classes.values()[0]
        in_args.insert(0, single_class)
    else:
        no_class, single_class = False, False
    # Parsing Ends Here
    if not single_class and (not in_args or in_args[0] == '--help'):
        # if os.environ.has_key('COMP_LINE'):
        #     os.system(                         "logger -t 'PY_PARSE_M2' '%s'" % str('>>'+os.environ['COMP_LINE']+'<<'))
        # else:
        #     os.system(                         "logger -t 'PY_PARSE_M2' '%s'" % str('>>'+str(in_args)+'<<'))
        tmp_usage = '\n\t' + p.format_usage().split()[1]
        sp = p.add_subparsers()
        for k, v in sorted(avail_classes.items()):
            sp.add_parser(v, help=getattr(mod, k).__doc__)

        sp.metavar = 'FUNCTION_CLASS'
        p.usage = tmp_usage + ' %s [--help]' % sp.metavar
        argcomplete.autocomplete(p)
        if DEBUG_PARSING: print print_line_number()
        return p.parse_args()
    # Unrecognized Parse instruction
    if not avail_classes.values().count(in_args[0]):
        # if os.environ.has_key('COMP_LINE'):
        #     os.system(                         "logger -t 'PY_PARSE_M3' '%s'" % str('>>'+os.environ['COMP_LINE']+'<<'))
        # else:
        #     os.system(                         "logger -t 'PY_PARSE_M3' '%s'" % str('>>'+str(in_args)+'<<'))
        print 'Unrecognized <class>'
        print in_args
        p.print_help()
        import sys
        if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
        sys.exit(1)
    # Execute Parse instruction
    else:
        # if os.environ.has_key('COMP_LINE'):
        #     os.system(                         "logger -t 'PY_PARSE_M4' '%s'" % str('>>'+os.environ['COMP_LINE']+'<<'))
        # else:
        #     os.system(                         "logger -t 'PY_PARSE_M4' '%s'" % str('>>'+str(in_args)+'<<'))
        p_help = argparse.SUPPRESS if [ it for it in in_args if not it == '--help' ] else 'Functions to operate'
        p.add_argument('_class', help=p_help, choices=sorted(avail_classes.values()))
        p.usage = p.format_usage().replace('usage: ', '', 1).replace('[--help] {_class}', in_args[0] + ' [--help]')
        if DEBUG_PARSING: print 'LINE:',inspect.getframeinfo(inspect.currentframe()).lineno
        return parse_module_or_class(getattr(mod, avail_classes.keys()[avail_classes.values().index(in_args[0])])(), p, in_args)


def run_custom_argparse(kwargs = None):
    if kwargs:
        for k, v in kwargs.iteritems():
            globals().update({k: v})

    mod_regex = '' if not globals().has_key('mod_regex') else mod_regex
    mod_excludes = [] if not globals().has_key('mod_excludes') else mod_excludes
    MODULE = inspect.stack()[-1][1]
    c = parse_module(mod_path=MODULE, regex=mod_regex, excludes=mod_excludes)
    if not c:
        raise SystemExit
    if type(c) == tuple:
        c = c[0]
    if no_class or hasattr(c, '_class'):
        import imp
        mod = imp.load_source('', MODULE)
        class_func = mod if not hasattr(c, '_class') else getattr(mod, c._class)()
        return_var = getattr(class_func, c._func)(c)
    else:
        D = {}
        D.update(locals())
        for k, v in D.iteritems():
            if re.findall(mod_regex, k) and inspect.isclass(v) and not mod_excludes.count(k):
                print v
                if re.sub(mod_regex, '\\1', k).lower() == c._class:
                    THIS_CLASS = v()
                    break

        return_var = getattr(THIS_CLASS, c._func)(c)
    if return_var:
        print return_var
