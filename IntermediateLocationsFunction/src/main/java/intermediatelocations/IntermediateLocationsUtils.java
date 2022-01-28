package intermediatelocations;

import java.util.ArrayList;
import java.util.List;

import com.amazonaws.services.lambda.runtime.events.models.dynamodb.AttributeValue;


public class IntermediateLocationsUtils {
    public static final String UPDATER_TABLE = "UpdaterHistoricalTable";
    public static final String INTERMEDIATE_QUEUE = "IntermediateLocationsQueue";
    public static final String INSERT = "INSERT";
    public static final String MODIFY = "MODIFY";
    public static final String REMOVE = "REMOVE";
    
    public static final String EPC = "Epc";
    public static final String DEVICE_ID = "Device_id";
    public static final String TIMESTAMP = "Timestamp";
    public static final String AREA_ID = "Area_id";
    public static final String UPDATER_POSE = "Updater_pose";
    public static final String CHANNEL_ESTIMATES = "Channel_estimates";

    /**
     * Given a List of AttributeValues, each of which represents a List pair of AttributeValues that 
     * in turn represent Doubles, returns the corresponding List of List pairs of Doubles.
     * 
     * @param originalChannelEstimates
     * @return
     */
    public static List<List<Double>> convertChannelEstimates(final List<AttributeValue> originalChannelEstimates) {
        List<List<Double>> convertedChannelEstimates = new ArrayList<>();
        for (AttributeValue channelEstimatePair : originalChannelEstimates) {
            // Each channelEstimatePair should start as form [AttributeValue, AttributeValue] and
            // end up as [Double, Double]
            List<AttributeValue> chanEstPairList = channelEstimatePair.getL();
            convertedChannelEstimates.add(List.of(
                Double.parseDouble(chanEstPairList.get(0).getN()),
                Double.parseDouble(chanEstPairList.get(1).getN())
                ));
        }

        return convertedChannelEstimates;
    }
}
