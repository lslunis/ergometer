#import <AppKit/NSEvent.h>
#import <stdio.h>
#import "AppDelegate.h"

enum {
    ErgoId,
    ErgoKey,
    ErgoMeta,
    ErgoRepeat,
    ErgoMove,
    ErgoClick,
    ErgoScroll,
    ErgoDrag,
    ErgoError,
    ErgoStatus
};

@interface AppDelegate ()

@property (weak) IBOutlet NSWindow *window;
@property NSMutableArray *sample;
@property NSMutableArray *record;

@end


@implementation AppDelegate

- (long long)sampleId
{
    return (long long)([[NSDate date] timeIntervalSince1970] * 10);
}

- (long long)recordId
{
    return (long long)([[NSDate date] timeIntervalSince1970]);
}

- (void)reset:(NSMutableArray *)array at:(long long)id
{
    [array removeAllObjects];
    array[ErgoId] = @(id);
}

- (BOOL)resampled:(NSUInteger)col sub:(NSUInteger)subcol
{
    if (col < [self.sample count]) {
        NSObject *obj = self.sample[col];
        if ([obj isKindOfClass:[NSMutableArray class]]) {
            NSMutableArray *array = (NSMutableArray *)obj;
            return subcol < [array count] && [array[subcol] isKindOfClass:[NSNumber class]] &&
            !![array[subcol] longLongValue];
        } else {
            return [obj isKindOfClass:[NSNumber class]] && !![(NSNumber *)obj longLongValue];
        }
    }
    return NO;
}

- (void)vivify:(NSMutableArray *)array at:(NSUInteger)index using:(NSUInteger)action
{
    NSUInteger end;
    while ((end = [array count]) <= index) {
        array[end] = @"";
    }
    
    if (action == NSNotFound) {
        long long x = [([array[index] isKindOfClass:[NSNumber class]] ?
                        array[index] : 0) longLongValue];
        array[index] = @(x + 1);
    } else {
        if (![array[index] isKindOfClass:[NSMutableArray class]]) {
            array[index] = [[NSMutableArray alloc] init];
        }
        [self vivify:array[index] at:action using:NSNotFound];
    }
}

- (void)log
{
    NSMutableArray *parts = [[NSMutableArray alloc] init];
    for (NSObject *obj in self.record) {
        if ([obj isKindOfClass:[NSArray class]]) {
            [parts addObject:[(NSArray *)obj componentsJoinedByString:@" "]];
        } else {
            [parts addObject:[obj description]];
        }
    }
    NSString *string = [[parts componentsJoinedByString:@","] stringByAppendingString:@"\n"];
    
    NSString *path = [@"~/Cellar/log/rsi-meter.log" stringByStandardizingPath];
    FILE *file = fopen([path UTF8String], "a");
    if (!file) {
        return;
    }
    
    fputs([string UTF8String], file);
    fclose(file);
}

- (void)applicationDidFinishLaunching:(NSNotification *)notification
{
    self.sample = [[NSMutableArray alloc] init];
    [self reset:self.sample at:[self sampleId]];
    
    self.record = [[NSMutableArray alloc] init];
    [self reset:self.record at:[self recordId]];
    
    NSEventMask mask =
    NSKeyDownMask |
    NSFlagsChangedMask |
    NSLeftMouseDownMask |
    NSRightMouseDownMask |
    NSOtherMouseDownMask |
    NSScrollWheelMask |
    NSMouseMovedMask |
    NSLeftMouseDraggedMask |
    NSRightMouseDraggedMask |
    NSOtherMouseDraggedMask;
    
    [NSEvent addGlobalMonitorForEventsMatchingMask:mask handler:^(NSEvent *e) {
        long long recordId = [self recordId];
        // If the system clock is adjusted pastward while the program is running, events will
        // be coalesed into a single large interval, maintaining logfile monoticity.
        if (recordId > [self.record[ErgoId] longLongValue]) {
            [self log];
            [self reset:self.record at:recordId];
        }
        
        NSUInteger col;
        NSUInteger subcol = NSNotFound;
        NSEventType t = [e type];
        switch (t) {
            case NSKeyDown:
            case NSFlagsChanged:
            {
                col = t == NSKeyDown ? [e isARepeat] ? ErgoRepeat : ErgoKey : ErgoMeta;
                NSUInteger flags = [e modifierFlags];
                subcol =
                !!(flags & NSShiftKeyMask) +
                !!(flags & NSControlKeyMask) +
                !!(flags & NSAlternateKeyMask) +
                !!(flags & NSCommandKeyMask);
                break;
            }
            case NSMouseMoved:
                col = ErgoMove;
                break;
            case NSLeftMouseDown:
            case NSRightMouseDown:
            case NSOtherMouseDown:
                col = ErgoClick;
                break;
            case NSScrollWheel:
                col = ErgoScroll;
                break;
            case NSLeftMouseDragged:
            case NSRightMouseDragged:
            case NSOtherMouseDragged:
                col = ErgoDrag;
                break;
            default:
                col = ErgoError;
        }
        
        
        BOOL shouldVivifyRecord = YES;
        if (col == ErgoRepeat || col == ErgoMove || col == ErgoScroll || col == ErgoDrag) {
            long long sampleId = [self sampleId];
            if (sampleId > [self.sample[ErgoId] longLongValue]) {
                [self reset:self.sample at:sampleId];
            }
            
            if ([self resampled:col sub:subcol]) {
                shouldVivifyRecord = NO;
            } else {
                [self vivify:self.sample at:col using:subcol];
            }
        }
        
        if (shouldVivifyRecord) {
            [self vivify:self.record at:col using:subcol];
        }
    }];
}

- (void)applicationWillTerminate:(NSNotification *)notification
{
    [self log];
}

@end
