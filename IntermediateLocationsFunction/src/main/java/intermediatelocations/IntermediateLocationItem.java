package intermediatelocations;

import java.util.List;
import java.util.Map;

import com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBAttribute;
import com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBHashKey;
import com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBRangeKey;
import com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBTable;

@DynamoDBTable(tableName="IntermediateLocationsQueue")
public class IntermediateLocationItem {
    private String deviceId;
    private String epc;
    private String areaId;
    private long timestamp;
    private Map<String, Double> updaterPose;
    private List<List<Double>> channelEstimates;

    @DynamoDBHashKey(attributeName = "Device_id")
    public String getDeviceId() { return deviceId; }
    public void setDeviceId(String deviceId) { this.deviceId = deviceId; }

    @DynamoDBRangeKey(attributeName = "Epc")
    public String getEpc() { return epc; }
    public void setEpc(String epc) { this.epc = epc; }

    @DynamoDBAttribute(attributeName = "Area_id")
    public String getAreaId() { return areaId; }
    public void setAreaId(String areaId) { this.areaId = areaId; }

    @DynamoDBAttribute(attributeName = "Timestamp")
    public long getTimestamp() { return timestamp; }
    public void setTimestamp(long timestamp) { this.timestamp = timestamp; }

    @DynamoDBAttribute(attributeName = "Updater_pose")
    public Map<String, Double> getUpdaterPose() { return updaterPose; }
    public void setUpdaterPose(Map<String, Double> updaterPose) { this.updaterPose = updaterPose; }

    @DynamoDBAttribute(attributeName = "Channel_estimates")
    public List<List<Double>> getChannelEstimates() { return channelEstimates; }
    public void setChannelEstimates(List<List<Double>> channelEstimates) { this.channelEstimates = channelEstimates; }

}
