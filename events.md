i want to be able to indicate handler order by:
    - priority (finite integer steps)
    - relative position (my handler must come after some handler and before some other)
        - need to be able to be relative both to "tags" or "groups", and to specific handlers
        - need to be able to mark a handler as "providing" another handler, if it does the same job
        - what happens when a handler is "before" a missing handler/tag, or "after" a missing handler/tag?
            - need handlers to be able to "require" being before - error if not possible -
                             and "suggest" being before - if not possible, don't bother
        - should priority be done with tags?
    - event state?

how should resolving handler order work?
    - probably want to use a dependency sort algorithm
        1. resolve all tags/references
            - resolve string references to real references to the handlers
                - should be done by matching registered handlers, not by looking up
                        handlers in the python module structure
                    - use glob, if grouping is needed extend glob manually
                - error if no matches found?
            - look up in registration dict, and if the registration has a tag,
                    replace reference with that tag
            - how do we deal with bound methods?
                - ideally they'd all be a single entity
                    - they probably should be registered as a single entity and managed
                            by the other class, so let's not special case them
            
        2. flip reverse dependencies
        3. merge all same-tagged items
        4. then simple topological sort
    - how should handlers reference other handlers?
        - by name and reference, at least; tags by name only
            - how flexible should name resolving be?
            - what happens when a named reference is not available?
                - perhaps it should error, and then the only way to do "optional" references
                        would be with tags?
                    - need to be explicit in the error output, as it won't be from the
                            same place registration happens
    - how should "permanent" tags work? ie, priority tags
        - same as normal tags, except the tag groups depend on each other?
    - do we really want to merge tags into one? plugins could create mysterious problems
            for each other
        - how else are we going to do it?
            - perhaps tagged items must share the same dependency lists?
                - different to merging because merging creates a total dependency list,
                        which would only cause errors if the sum of all dependencies are
                        unresolvable
            - or tagged items must not have any dependencies
            - there could be a "set tag dependencies" call, which adds dependencies
                    to a tag, which must then be shared between everything
                - this is definitely how priority tags should work; exposing it would
                    be nice too

should multiple tags be allowed?
    - seems like it'd be hard to be useful

how should things that depend on tagged handlers directly be dealt with?
        that is, if my handler x depends on y, and y is tagged "atag",
        then y will be grouped with atag; so, where should x be placed?
    - should the reference simply be changed to the tag? ie, x would now depend
        on atag
     asdf

what identification should be used during dependency resolution?
    - probably reference

should tags and dependency information be independent of hook?
    - what if we have a circumstance where we need it to be hook-specific?
        - could have both global and hook-local order information
    - perhaps a hook.order decorator which sets the callable's global order information in
            a special attribute?
        - what if we only want the order information to be for some hooks?
            - tough luck, I guess you'll have to copy it - this is too much of a special circumstance
    - how would we manipulate the dependency information on global tags?
        - would have to have a global list of all tags
            - yucky, module-globals are ick


how should event cancelling be handled? should cancelled events continue to be passed?
    - cancelled events should skip handlers which are not marked "ignore-cancelled"
        - this can be done much more nicely than in java

should handlers be able to mark conditions about the event?
    - this would just be moving code that could be in the top of the handler
    - it may be much more concise and understandable, though
        - also might be able to optimize - for instance, command events; don't want to iterate all
                 handlers if it can be avoided, rather just iterate the ones that are known will match
    - event classes should have some control over what handlers are called
        - to this end, event classes will subclass Hook
    - for instance, what if I only care about messages sent to a particular channel?
         should I filter the channel with an if at the top of the handler, or do it by saying
         @hook.whatever(..., channel="#mychannel")?

what should class-instantiation handlers be used for?
    - they're good at anything with state, which doesn't have a logical flow of events
    - how should they be garbage collected? classes have no "end condition" as they are not
            normally used for such things; should a special "I'm done" method be added to the class?
    - should classes be able to specify singletonness? ie, should classes be able to say "there
         should never be more than one of me"?
        - probably not, because this can easily be enforced by the class itself

what about yield-generator handlers? should I need to do a special decoration to mark it
        as a yield-handler? or should it detect it and automatically wrap it?
    - automatic detection would work by checking if the callable returned an iterator
        - need to try out - could allow other kinds of iterator-factories, such as classes
            - or would it? those would work fine with a special decorator, too - there's fundamentally
                    no way to tell if the callable itself is a generator factory without calling it

what should hooks pass to their handlers?
    - probably a dict which allows access to it's members via attributes, such as skybot does
    - hooks should be free to pass whatever they like
        - how should cancelled-ness and the like be represented if hooks can pass whatever, though?
        - perhaps instead of being free to pass whatever, the hook automatically
        - creates an event object based on the information it is called with? ie, call the 
                constructor of an event object based on call information
    - how would this integrate with cancelling and similar?

how should event call context be handled?
    - perhaps a context object, similar to re_gen.base.Creator, which automatically adds
         context to the calls when calling an event; would look like self.hookcontext.privmsg()
         or something when used
    - alternately, "context" dicts which get passed around
        - for instance, hook.fire(self.context, callcontext, my=value, my=value)
            - all *args would be joined into a single dict
            - that dict would then be updated with **keywords

how should hook heirarchies be handled? for instance, privmsg -> message -> event
    - a goal of heirarchies is to allow easier construction of events contextually
            for instance, if we're in a privmsg handler, we would prefer to not have to
            construct the "message" portion manually - see "context" question
    - another goal of heirarchies is to allow handlers to register to a whole category
            of events; for instance, if I want to do raw message logging, I want to
            monitor all incoming messages
        - this could be done by firing a message event and then a more specific event;
                is this an acceptable solution?
            - perhaps heirarchies could do this automatically?
    - perhaps heirarchial events could subclass both Hook and HookCategory
        - this should somehow turn into automatically calling parents when calling a child
    - we want control over how the heirarchy works when creating it; for instance, some
            may just be a simple category with no parent-event-calls, while others may be
            may have parent calls
        - could have a pre-mixed-in superclass for this

class instantiation
    - method superclass overriding:
        - need to be able to keep hooks from superclass from activating
        - best way to do this is probably just to use the methods from the bottom of the MRO;
                after all, you can just name the methods new things to avoid doing this
    - should they need to be run through hook.instantiate, or should the standard
            hook execution loop detect created classes and prepare their method hooks?
        - I like the explicitness of hook.instantiate, but I also think that unnecessary
                confusion between the different kinds of registrations could be bad

the hook class needs to have good support for subclassing
    - things should be devided up logically, and call around a fair amount
        - however, not excessively, as this will be the most-called anything in the app

should have some sort of namespace for special, automatically-added attributes
    - perhaps _crowevents_%s_? doesn't need to be fancy, just guaranteed unique

how should hook.once() work? should it be a decorator?
    - could wrap the callable in a function which will unregister itself after being called
    - could add it to a special list of only-one-call hooks

how should registrations be represented?
    - namedtuple?
    - class?
    - dict?
    - do we want to separate instructions for the hook - such as
            tag/tags/priority/order/before/after/etc - from inst...
        - wait, no, because of the hook subclassing scheme, EVERYTHING is instructions
                for the hook. the only way to make a special hook *is to subclass*.
                this is brilliant.
    - okay so do we want to have any special representation for method registrations?
        - probably not, just store how they were registered and do the real
                handling of registration options when they're
                loaded at class instantiation
    - namedtuple for method 

registration, AttrDict for normal registration?
        

what arguments should be available to indicate order?
    - before - string or other iterable which produces strings
        - lone string gets special treatment?
    - after
        - same behavior as `before`
    - tag - allows setting a single tag,
    - tags - allows setting multiple tags
        - these could be merged the same way as before and after

tag resolving - we don't need to resolve to anything that isn't registered

should dependency reference resolution provide a way to access other packages?

should provide a way to treat dependency loops as warnings
